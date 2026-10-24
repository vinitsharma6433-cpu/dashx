"""DASHX Auto Poster. Posts due items from poster/queue.json to YouTube, Facebook and Instagram.
Runs inside GitHub Actions every 15 minutes. Secrets come from environment variables.
A network without its secrets is skipped (status stays 'scheduled' for that network)."""
import json, os, sys, time, datetime as dt
import requests

QUEUE = os.path.join(os.path.dirname(__file__), "queue.json")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
G = "https://graph.facebook.com/v21.0"

def env(*names):
    vals = [os.environ.get(n, "").strip() for n in names]
    return vals if all(vals) else None

def get_media(url):
    r = requests.get(url, timeout=300); r.raise_for_status(); return r.content

# ---------- YouTube Short ----------
def post_youtube(p):
    s = env("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")
    if not s: return None
    t = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": s[0], "client_secret": s[1], "refresh_token": s[2], "grant_type": "refresh_token"}, timeout=60)
    if not t.ok:
        try: e = t.json()
        except Exception: e = {}
        raise RuntimeError("google token error: %s - %s | id_len=%d secret_len=%d token_len=%d" % (e.get("error"), e.get("error_description"), len(s[0]), len(s[1]), len(s[2])))
    tok = t.json()["access_token"]
    title = (p.get("yt_title") or p["title"])[:95]
    meta = {"snippet": {"title": title, "description": p.get("captions", {}).get("youtube") or p["caption"],
                        "tags": ["DASHX", "gully cricket", "Meerut"], "categoryId": "24"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    data = get_media(p["media"])
    h = {"Authorization": "Bearer " + tok, "Content-Type": "application/json; charset=UTF-8",
         "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(len(data))}
    i = requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                      headers=h, data=json.dumps(meta), timeout=60)
    i.raise_for_status()
    u = requests.put(i.headers["Location"], data=data, headers={"Content-Type": "video/mp4"}, timeout=600)
    u.raise_for_status()
    return "https://www.youtube.com/shorts/" + u.json()["id"]

# ---------- Facebook Page Reel ----------
def post_facebook(p):
    s = env("META_PAGE_TOKEN", "FB_PAGE_ID")
    if not s: return None
    tok, page = s
    a = requests.post(f"{G}/{page}/video_reels", data={"upload_phase": "start", "access_token": tok}, timeout=60)
    a.raise_for_status(); vid = a.json()["video_id"]; up = a.json()["upload_url"]
    b = requests.post(up, headers={"Authorization": "OAuth " + tok, "file_url": p["media"]}, timeout=300)
    b.raise_for_status()
    c = requests.post(f"{G}/{page}/video_reels", data={
        "upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
        "description": p.get("captions", {}).get("facebook") or p["caption"], "title": p["title"][:90],
        "access_token": tok}, timeout=120)
    c.raise_for_status()
    return "https://www.facebook.com/reel/" + vid

# ---------- Instagram Reel ----------
def post_instagram(p):
    s = env("META_PAGE_TOKEN", "IG_USER_ID")
    if not s: return None
    tok, ig = s
    a = requests.post(f"{G}/{ig}/media", data={"media_type": "REELS", "video_url": p["media"],
        "caption": p.get("captions", {}).get("instagram") or p["caption"], "share_to_feed": "true",
        "access_token": tok}, timeout=120)
    a.raise_for_status(); cid = a.json()["id"]
    for _ in range(40):
        st = requests.get(f"{G}/{cid}", params={"fields": "status_code", "access_token": tok}, timeout=60).json()
        if st.get("status_code") == "FINISHED": break
        if st.get("status_code") == "ERROR": raise RuntimeError("Instagram processing error")
        time.sleep(15)
    b = requests.post(f"{G}/{ig}/media_publish", data={"creation_id": cid, "access_token": tok}, timeout=120)
    b.raise_for_status()
    return "instagram:" + b.json()["id"]

HANDLERS = {"youtube": post_youtube, "facebook": post_facebook, "instagram": post_instagram}

def main():
    q = json.load(open(QUEUE, encoding="utf-8"))
    now = dt.datetime.now(IST); changed = False
    for p in q["posts"]:
        due = dt.datetime.fromisoformat(p["when"])
        if p.get("status") == "done" or due > now: continue
        res = p.setdefault("results", {})
        for net in p["networks"]:
            if net in res and res[net].get("ok"): continue
            fn = HANDLERS.get(net)
            if not fn:
                res[net] = {"ok": False, "error": "network not supported yet"}; changed = True; continue
            try:
                link = fn(p)
                if link is None:
                    res[net] = {"ok": False, "error": "secrets missing, add them in repo Settings"}
                else:
                    res[net] = {"ok": True, "link": link, "at": now.isoformat()}
                changed = True
            except Exception as e:
                res[net] = {"ok": False, "error": str(e)[:300]}; changed = True
        if all(res.get(n, {}).get("ok") for n in p["networks"]): p["status"] = "done"
    if changed: json.dump(q, open(QUEUE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print("run ok", now.isoformat())

if __name__ == "__main__":
    main()
