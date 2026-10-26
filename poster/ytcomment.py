import os, sys, json, requests
r = requests.post("https://oauth2.googleapis.com/token", data={"client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"], "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"}, timeout=60)
if not r.ok: print("token error", r.status_code, r.json().get("error")); sys.exit(1)
tok = r.json()["access_token"]; hdr = {"Authorization": "Bearer " + tok}
jobs = json.load(open("poster/ytcomment.json"))
out = []
for j in jobs:
    vid = j["video"]; res = {"video": vid}
    for t in j["comments"]:
        c = requests.post("https://www.googleapis.com/youtube/v3/commentThreads?part=snippet", headers=hdr, json={"snippet": {"videoId": vid, "topLevelComment": {"snippet": {"textOriginal": t}}}}, timeout=60)
        res.setdefault("comments", []).append(c.status_code)
    l = requests.post("https://www.googleapis.com/youtube/v3/videos/rate?id=%s&rating=like" % vid, headers=hdr, timeout=60)
    res["like"] = l.status_code; out.append(res); print(res)
json.dump(out, open("poster/ytcomment_result.json", "w"))
