"""DASHX Auto Poster. Posts due items from poster/queue.json to YouTube, Facebook and Instagram.
Runs inside GitHub Actions every 15 minutes. Secrets come from environment variables.
A network without its secrets is skipped (status stays 'scheduled' for that network)."""
import json, os, subprocess, sys, time, datetime as dt
import requests

QUEUE = os.path.join(os.path.dirname(__file__), "queue.json")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
G = "https://graph.facebook.com/v21.0"

def env(*names):
    vals = [os.environ.get(n, "").strip() for n in names]
    return vals if all(vals) else None

def get_media(url):
    r = requests.get(url, timeout=300); r.raise_for_status(); return r.content

# GitHub cron can run hours late, so a YouTube entry is uploaded up to LOOKAHEAD_H hours BEFORE its `when`
# as a private video with publishAt = when. YouTube then makes it public on time, whatever the cron does.
LOOKAHEAD_H = 36
FB_LOOKAHEAD = dt.timedelta(hours=24)       # Facebook Reels are scheduled up to this long before their slot (Meta: SCHEDULED + scheduled_publish_time)
FB_MIN_AHEAD = dt.timedelta(minutes=15)       # Meta needs the time to be at least ~10 minutes ahead
MIN_PUBLISH_AHEAD = dt.timedelta(minutes=15)  # publishAt must be in the future; closer than this = publish now

# ---------- YouTube Short ----------
def yt_token():
    s = env("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")
    if not s: return None
    t = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": s[0], "client_secret": s[1], "refresh_token": s[2], "grant_type": "refresh_token"}, timeout=60)
    if not t.ok:
        try: e = t.json()
        except Exception: e = {}
        raise RuntimeError("google token error: %s - %s | id_len=%d secret_len=%d token_len=%d" % (e.get("error"), e.get("error_description"), len(s[0]), len(s[1]), len(s[2])))
    return t.json()["access_token"]

def yt_engage(p, vid, tok):
    """Pinned-style comments and a like. Only works once the video is public."""
    notes = p.setdefault("notes", {})
    hdr = {"Authorization": "Bearer " + tok}
    cl = p.get("comments") or ([p["comment"]] if p.get("comment") else [])
    res = []
    for ctext in cl:
        try:
            cr = requests.post("https://www.googleapis.com/youtube/v3/commentThreads?part=snippet", headers=hdr,
                json={"snippet": {"videoId": vid, "topLevelComment": {"snippet": {"textOriginal": ctext}}}}, timeout=60)
            res.append("ok" if cr.ok else "failed %s (needs youtube.force-ssl scope)" % cr.status_code)
        except Exception as e:
            res.append("error " + str(e)[:80])
    if res: notes["yt_comment"] = res
    try:
        rr = requests.post("https://www.googleapis.com/youtube/v3/videos/rate?id=%s&rating=like" % vid, headers=hdr, timeout=60)
        notes["yt_like"] = "ok" if rr.status_code in (200, 204) else "failed %s" % rr.status_code
    except Exception as e:
        notes["yt_like"] = "error " + str(e)[:80]

def post_youtube(p, publish_at=None):
    """publish_at (aware datetime) = upload private and let YouTube publish it then; None = public now.
    Returns the Shorts link, or None when the secrets are missing."""
    tok = yt_token()
    if not tok: return None
    title = (p.get("yt_title") or p["title"])[:95]
    status = {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
    if publish_at is not None:
        status = {"privacyStatus": "private", "selfDeclaredMadeForKids": False,
                  "publishAt": publish_at.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")}
    meta = {"snippet": {"title": title, "description": p.get("captions", {}).get("youtube") or p["caption"],
                        "tags": ["DASHX", "gully cricket", "Meerut"], "categoryId": "24"},
            "status": status}
    data = get_media(p["media"])
    h = {"Authorization": "Bearer " + tok, "Content-Type": "application/json; charset=UTF-8",
         "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(len(data))}
    i = requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                      headers=h, data=json.dumps(meta), timeout=60)
    i.raise_for_status()
    u = requests.put(i.headers["Location"], data=data, headers={"Content-Type": "video/mp4"}, timeout=600)
    u.raise_for_status()
    vid = u.json()["id"]
    p.setdefault("notes", {})["yt_video_id"] = vid
    if publish_at is None:
        yt_engage(p, vid, tok)
    return "https://www.youtube.com/shorts/" + vid

# ---------- Meta (Facebook + Instagram) ----------
MAX_META_TRIES = 3   # a failing Facebook/Instagram post is retried this many times, then left alone (no duplicate-post risk)
TOKEN_BAD = {"flag": False}

class MetaError(Exception):
    pass

def _scrub(text, tok):
    text = str(text)
    return text.replace(tok, "<token>") if tok else text

def meta_check(r, tok, what):
    """Raise a MetaError with a clear text (never the token) when the Graph API answers with an error."""
    if r.ok:
        return r
    try:
        e = r.json().get("error", {})
    except Exception:
        e = {}
    code, sub = e.get("code"), e.get("error_subcode")
    msg = _scrub(e.get("message") or ("HTTP %s" % r.status_code), tok)[:220]
    if code in (190, 102) or sub in (458, 459, 460, 463, 467) or (code == 200 and "Cannot call API for app" in str(e.get("message", ""))):
        TOKEN_BAD["flag"] = True
        print("::error::META TOKEN INVALID or EXPIRED (%s, Graph code %s/%s): %s. Make a new non-expiring Page token and update the META_PAGE_TOKEN secret." % (what, code, sub, msg))
        raise MetaError("META TOKEN INVALID/EXPIRED (code %s/%s): %s" % (code, sub, msg))
    raise MetaError("%s failed (code %s/%s): %s" % (what, code, sub, msg))

def check_public_video(url):
    """Instagram and Facebook fetch the video from this URL themselves, so it must be public and a real video."""
    r = requests.head(url, allow_redirects=True, timeout=60)
    if r.status_code != 200:
        r = requests.get(url, stream=True, timeout=60); r.close()
    if r.status_code != 200:
        raise MetaError("video URL is not public (HTTP %s): %s" % (r.status_code, url))
    ct = r.headers.get("Content-Type", "")
    if "video" not in ct and "octet-stream" not in ct:
        raise MetaError("video URL does not serve a video (Content-Type %s): %s" % (ct, url))

def meta_comments(p, target_id, tok, key):
    """First comment(s) with the buy links. A comment failure never turns a published post into a failure: it is only noted."""
    notes = p.setdefault("notes", {})
    cl = p.get("comments") or ([p["comment"]] if p.get("comment") else [])
    out = []
    for text in cl:
        try:
            r = requests.post(f"{G}/{target_id}/comments", data={"message": text, "access_token": tok}, timeout=60)
            meta_check(r, tok, key + " comment")
            out.append("ok")
        except Exception as e:
            out.append("failed: " + _scrub(e, tok)[:150])
    if out: notes[key + "_comment"] = out

# ---------- Facebook Page Reel ----------
def post_facebook(p, publish_at=None):
    """publish_at (aware datetime) = upload now and let Facebook publish it then (video_state SCHEDULED, no cron needed); None = publish now."""
    s = env("META_PAGE_TOKEN", "FB_PAGE_ID")
    if not s: return None
    tok, page = s
    check_public_video(p["media"])
    a = meta_check(requests.post(f"{G}/{page}/video_reels", data={"upload_phase": "start", "access_token": tok}, timeout=60), tok, "Facebook reel start")
    vid = a.json()["video_id"]; up = a.json()["upload_url"]
    meta_check(requests.post(up, headers={"Authorization": "OAuth " + tok, "file_url": p["media"]}, timeout=300), tok, "Facebook reel upload")
    fin = {"upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
           "description": p.get("captions", {}).get("facebook") or p["caption"], "title": p["title"][:90], "access_token": tok}
    if publish_at is not None:
        fin["video_state"] = "SCHEDULED"
        fin["scheduled_publish_time"] = int(publish_at.timestamp())
    meta_check(requests.post(f"{G}/{page}/video_reels", data=fin, timeout=120), tok,
               "Facebook reel schedule" if publish_at is not None else "Facebook reel publish")
    if publish_at is not None:
        # Facebook publishes it by itself at publish_at. The first comment is added by main() after that time.
        p.setdefault("notes", {})["fb_video_id"] = vid
        return "https://www.facebook.com/reel/" + vid
    # wait until Facebook has processed it (up to ~6 minutes), so a processing error is seen as an error
    state = ""
    for _ in range(24):
        st = requests.get(f"{G}/{vid}", params={"fields": "status", "access_token": tok}, timeout=60)
        if st.ok:
            vs = (st.json().get("status") or {}).get("video_status", "")
            state = vs
            if vs in ("ready", "published"): break
            if vs == "error": raise MetaError("Facebook processing error: %s" % str(st.json().get("status"))[:200])
        time.sleep(15)
    p.setdefault("notes", {})["fb_video_id"] = vid
    p["notes"]["fb_status"] = state or "unknown"
    meta_comments(p, vid, tok, "fb")
    return "https://www.facebook.com/reel/" + vid

# ---------- Instagram Reel ----------
def post_instagram(p):
    s = env("META_PAGE_TOKEN", "IG_USER_ID")
    if not s: return None
    tok, ig = s
    check_public_video(p["media"])
    a = meta_check(requests.post(f"{G}/{ig}/media", data={"media_type": "REELS", "video_url": p["media"],
        "caption": p.get("captions", {}).get("instagram") or p["caption"], "share_to_feed": "true",
        "access_token": tok}, timeout=120), tok, "Instagram container create")
    cid = a.json()["id"]
    done = False
    for _ in range(40):   # up to ~10 minutes of processing
        r = requests.get(f"{G}/{cid}", params={"fields": "status_code,status", "access_token": tok}, timeout=60)
        meta_check(r, tok, "Instagram container status")
        sc = r.json().get("status_code")
        if sc == "FINISHED": done = True; break
        if sc in ("ERROR", "EXPIRED"): raise MetaError("Instagram processing %s: %s" % (sc, str(r.json().get("status"))[:200]))
        time.sleep(15)
    if not done: raise MetaError("Instagram container not finished after 10 minutes")
    b = meta_check(requests.post(f"{G}/{ig}/media_publish", data={"creation_id": cid, "access_token": tok}, timeout=120), tok, "Instagram publish")
    mid = b.json()["id"]
    p.setdefault("notes", {})["ig_media_id"] = mid
    link = "instagram:" + mid
    try:
        pl = requests.get(f"{G}/{mid}", params={"fields": "permalink", "access_token": tok}, timeout=60)
        if pl.ok and pl.json().get("permalink"): link = pl.json()["permalink"]
    except Exception:
        pass
    meta_comments(p, mid, tok, "ig")
    return link

HANDLERS = {"youtube": post_youtube, "facebook": post_facebook, "instagram": post_instagram}

# ---------- persistence: every result is saved (and pushed) the moment it exists ----------
LATE_H = 48   # a post whose slot is older than this is never posted late: it is marked skipped (protects against old or deliberately skipped reels)

def save_entry(p):
    """Write ONE entry into the CURRENT queue.json (re-read from disk), so entries that the factory added in the meantime are never lost."""
    try:
        cur = json.load(open(QUEUE, encoding="utf-8"))
    except Exception:
        return
    key = (p.get("media"), p.get("when"))
    for i, e in enumerate(cur["posts"]):
        if (e.get("media"), e.get("when")) == key:
            cur["posts"][i] = p
            break
    json.dump(cur, open(QUEUE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

def checkpoint(msg="Poster: checkpoint"):
    """Loop mode only (POSTER_CHECKPOINT=1): commit + push right after each result, so a crash or cancel can never lead to a duplicate post."""
    if os.environ.get("POSTER_CHECKPOINT") != "1": return
    try:
        subprocess.run(["git", "add", "poster/queue.json"], check=False)
        if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
            subprocess.run(["git", "commit", "-q", "-m", msg], check=False)
        for i in range(4):
            if subprocess.run("git pull --rebase -q --autostash origin main && git push -q origin HEAD:main", shell=True).returncode == 0: return
            subprocess.run(["git", "rebase", "--abort"], check=False)
            time.sleep(3 * (i + 1))
        print("::warning::checkpoint push failed; the loop retries after its next check")
    except Exception as e:
        print("::warning::checkpoint error: %s" % str(e)[:120])

def persist(p):
    save_entry(p)
    checkpoint()

def handle(p, now):
    due = dt.datetime.fromisoformat(p["when"])
    if p.get("status") == "done": return
    res = p.setdefault("results", {})
    # never post a reel late by more than LATE_H hours (old reels, reels skipped on purpose, long outages)
    if now - due > dt.timedelta(hours=LATE_H):
        for n in p["networks"]:
            r = res.get(n, {})
            if not r.get("ok") and not r.get("skipped_late"):
                res[n] = {"ok": False, "error": "skipped: slot older than %d h, not posted late" % LATE_H, "tries": 99, "skipped_late": True}
    if due > now:
        # not due yet: YouTube (36 h ahead) and Facebook (24 h ahead) are uploaded now and published by the platform itself at the slot
        yt = res.get("youtube", {})
        if ("youtube" in p["networks"] and not yt.get("ok") and due - now <= dt.timedelta(hours=LOOKAHEAD_H)
                and due - now > MIN_PUBLISH_AHEAD):
            try:
                link = post_youtube(p, publish_at=due)
                res["youtube"] = ({"ok": False, "error": "secrets missing, add them in repo Settings"} if link is None else
                                  {"ok": True, "link": link, "scheduled": True, "publish_at": p["when"], "at": now.isoformat()})
            except Exception as e:
                res["youtube"] = {"ok": False, "error": str(e)[:300]}
            persist(p)
        fb = res.get("facebook", {})
        if ("facebook" in p["networks"] and not fb.get("ok") and not fb.get("sched_failed") and fb.get("tries", 0) < MAX_META_TRIES
                and FB_MIN_AHEAD < due - now <= FB_LOOKAHEAD):
            try:
                link = post_facebook(p, publish_at=due)
                if link:
                    res["facebook"] = {"ok": True, "link": link, "scheduled": True, "publish_at": p["when"], "at": now.isoformat()}
            except Exception as e:
                # scheduling did not work: leave it to the normal post at the slot time (that path is unchanged)
                res["facebook"] = {"ok": False, "sched_failed": True, "error": "scheduling failed: " + _scrub(e, os.environ.get("META_PAGE_TOKEN", "").strip())[:250]}
                print("::warning::Facebook scheduling failed, it will be posted normally at its slot: %s" % res["facebook"]["error"])
            persist(p)
        return
    # YouTube first: Facebook/Instagram problems (slow processing, bad token) must never delay or block it
    for net in sorted(p["networks"], key=lambda n: n != "youtube"):
        yt = res.get(net, {})
        if yt.get("skipped_late"): continue
        if net == "youtube" and yt.get("ok") and yt.get("scheduled"):
            # published by YouTube at `when`: now add the comments and the like (once)
            if not p.get("notes", {}).get("yt_engaged"):
                try:
                    tok = yt_token()
                    if tok:
                        yt_engage(p, p["notes"]["yt_video_id"], tok)
                        p["notes"]["yt_engaged"] = True
                except Exception as e:
                    p.setdefault("notes", {})["yt_engage_error"] = str(e)[:200]
                persist(p)
            continue
        if net == "facebook" and yt.get("ok") and yt.get("scheduled"):
            notes = p.setdefault("notes", {})
            if not notes.get("fb_engaged") and notes.get("fb_comment_tries", 0) < 5:
                s_ = env("META_PAGE_TOKEN", "FB_PAGE_ID")
                if s_:
                    notes["fb_comment_tries"] = notes.get("fb_comment_tries", 0) + 1
                    notes.pop("fb_comment", None)
                    meta_comments(p, notes["fb_video_id"], s_[0], "fb")   # never raises; fails while the reel is not public yet -> retried next check
                    if notes.get("fb_comment") == ["ok"] or not (p.get("comments") or p.get("comment")):
                        notes["fb_engaged"] = True
                    persist(p)
            continue
        if net in res and res[net].get("ok"): continue
        fn = HANDLERS.get(net)
        if not fn:
            res[net] = {"ok": False, "error": "network not supported yet"}; persist(p); continue
        meta = net in ("facebook", "instagram")
        tries = res.get(net, {}).get("tries", 0)
        if meta and tries >= MAX_META_TRIES:
            continue   # gave up: retrying could post a duplicate. Fix the cause, then set results.<net> to {} in queue.json to retry
        try:
            link = fn(p)
            if link is None:
                res[net] = {"ok": False, "error": "secrets missing, add them in repo Settings"}
            else:
                res[net] = {"ok": True, "link": link, "at": now.isoformat()}
        except Exception as e:
            res[net] = {"ok": False, "error": _scrub(e, os.environ.get("META_PAGE_TOKEN", "").strip())[:300], "tries": tries + 1}
            if meta: print("::error::%s post failed (try %d of %d): %s" % (net, tries + 1, MAX_META_TRIES, res[net]["error"]))
        # save + push after every network, so a later crash can never make an already-published post run twice
        persist(p)
    notes_ = p.get("notes", {})
    engaged = all((not res.get(n, {}).get("scheduled")) or (notes_.get("fb_engaged") or notes_.get("fb_comment_tries", 0) >= 5 if n == "facebook" else notes_.get("yt_engaged"))
                  for n in p["networks"])
    if engaged and all(res.get(n, {}).get("ok") or res.get(n, {}).get("skipped_late") for n in p["networks"]):
        p["status"] = "done"
        persist(p)

def main():
    q = json.load(open(QUEUE, encoding="utf-8"))
    now = dt.datetime.now(IST)
    for p in q["posts"]:
        before = json.dumps(p, sort_keys=True)
        try:
            handle(p, now)
        finally:
            if json.dumps(p, sort_keys=True) != before:
                persist(p)   # also marks skipped-late entries; cheap when nothing changed
    print("run ok", now.isoformat())
    if TOKEN_BAD["flag"]:
        # results are already saved; the red run (and GitHub's e-mail) tells the owner to replace the Meta token
        print("::error::META_PAGE_TOKEN is invalid or expired: Facebook/Instagram posts are failing. YouTube is not affected.")
        sys.exit(1)

if __name__ == "__main__":
    main()
