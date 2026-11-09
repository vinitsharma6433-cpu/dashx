"""Publishing Agent: OPTIONAL upload to YouTube through the official YouTube Data API v3 (OAuth 2.0). Standard
library only. It never runs unless AUTO_UPLOAD=true AND you have created your own OAuth client and authorised
your channel. Nothing here bypasses platform rules, quotas or limits: it counts quota units and stops at the limit.

Setup (done by you, once):
  1. Google Cloud Console: create a project, enable "YouTube Data API v3", create an OAuth client of type
     "Desktop app", download the JSON file.
  2. Put the file OUTSIDE the repository and set YOUTUBE_CLIENT_SECRET_FILE=<path> (environment or factory.env).
  3. python -m factory youtube-auth      (opens the consent page; the refresh token is stored in YOUTUBE_TOKEN_FILE)
  4. Set AUTO_UPLOAD=true when you are ready. Videos upload as PRIVATE and are scheduled (publishAt).
Secrets are only ever read from those files; they are never logged, stored in the database or shown in the dashboard.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import db, log
from .config import Config, secret_paths

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
THUMB_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"
QUOTA_UPLOAD, QUOTA_THUMB = 1600, 50  # official quota costs: videos.insert and thumbnails.set
CATEGORY_ID = "23"  # Comedy


class YouTubeError(Exception):
    def __init__(self, msg: str, recoverable: bool = False):
        super().__init__(msg)
        self.recoverable = recoverable


def http(method: str, url: str, headers: dict | None = None, data: bytes | None = None, timeout: int = 120) -> tuple[int, bytes, dict]:
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def status(cfg: Config) -> dict:
    p = secret_paths()
    cs, tok = Path(p["client_secret_file"]) if p["client_secret_file"] else None, Path(p["token_file"])
    return {"auto_upload": cfg.AUTO_UPLOAD, "client_secret_configured": bool(cs and cs.exists()), "authorised": tok.exists(),
            "ready_to_upload": bool(cfg.AUTO_UPLOAD and cs and cs.exists() and tok.exists())}


def _client() -> dict:
    p = secret_paths()["client_secret_file"]
    if not p or not Path(p).exists():
        raise YouTubeError("YOUTUBE_CLIENT_SECRET_FILE is not set or the file is missing")
    j = json.loads(Path(p).read_text(encoding="utf-8"))
    return j.get("installed") or j.get("web") or j


def authorise(open_browser: bool = True, port: int = 8085) -> None:
    """One-time consent in your browser (loopback redirect). Stores the refresh token in YOUTUBE_TOKEN_FILE."""
    import http.server
    import secrets as _s
    import webbrowser

    c = _client()
    state = _s.token_urlsafe(16)
    redirect = f"http://127.0.0.1:{port}/"
    url = AUTH_URL + "?" + urllib.parse.urlencode({"client_id": c["client_id"], "redirect_uri": redirect, "response_type": "code", "scope": SCOPE,
                                                    "access_type": "offline", "prompt": "consent", "state": state})
    box: dict = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            box["code"], box["state"] = (q.get("code") or [""])[0], (q.get("state") or [""])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"DASHX: authorised. You can close this tab.")

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", port), H)
    print("Open this address and allow access:\n" + url)
    if open_browser:
        webbrowser.open(url)
    srv.handle_request()
    if box.get("state") != state or not box.get("code"):
        raise YouTubeError("authorisation failed (state mismatch or no code)")
    body = urllib.parse.urlencode({"code": box["code"], "client_id": c["client_id"], "client_secret": c.get("client_secret", ""), "redirect_uri": redirect,
                                   "grant_type": "authorization_code"}).encode()
    st, resp, _ = http("POST", TOKEN_URL, {"Content-Type": "application/x-www-form-urlencoded"}, body)
    tok = json.loads(resp or b"{}")
    if st != 200 or "refresh_token" not in tok:
        raise YouTubeError(f"token exchange failed (HTTP {st})")
    path = Path(secret_paths()["token_file"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"refresh_token": tok["refresh_token"]}), encoding="utf-8")
    log.info("YouTube authorised; refresh token stored", name="youtube")


def access_token(transport=http) -> str:
    c = _client()
    tok = json.loads(Path(secret_paths()["token_file"]).read_text(encoding="utf-8"))
    body = urllib.parse.urlencode({"client_id": c["client_id"], "client_secret": c.get("client_secret", ""), "refresh_token": tok["refresh_token"],
                                   "grant_type": "refresh_token"}).encode()
    st, resp, _ = transport("POST", TOKEN_URL, {"Content-Type": "application/x-www-form-urlencoded"}, body)
    if st != 200:
        raise YouTubeError(f"could not refresh the access token (HTTP {st})", recoverable=st >= 500)
    return json.loads(resp)["access_token"]


def quota_used_today() -> int:
    day = time.strftime("%Y-%m-%d")
    rows = db.q("SELECT detail FROM uploads WHERE status='uploaded' AND ts LIKE ?", (day + "%",))
    return len(rows) * (QUOTA_UPLOAD + QUOTA_THUMB)


def build_metadata(meta: dict, publish_at: datetime | None, privacy: str) -> dict:
    snippet = {"title": meta["title"][:100], "description": meta["description"][:5000], "tags": meta["tags"], "categoryId": CATEGORY_ID,
               "defaultLanguage": "hi", "defaultAudioLanguage": "hi"}
    st = {"privacyStatus": "private" if publish_at else privacy, "selfDeclaredMadeForKids": False,
          "containsSyntheticMedia": True}  # honest AI-content disclosure
    if publish_at:
        st["publishAt"] = publish_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"snippet": snippet, "status": st}


def upload(video: Path, thumbnail: Path | None, meta: dict, cfg: Config, publish_at: datetime | None, transport=http, sleep=time.sleep) -> str:
    """Resumable upload + thumbnail. Retries recoverable errors (network, 5xx, 429) up to 3 times. Returns the video id."""
    last: Exception | None = None
    for attempt in range(1, 4):
        try:
            tok = access_token(transport)
            auth = {"Authorization": f"Bearer {tok}"}
            md = json.dumps(build_metadata(meta, publish_at, cfg.YOUTUBE_PRIVACY)).encode()
            st, _, hdr = transport("POST", UPLOAD_URL + "?uploadType=resumable&part=snippet,status",
                                   {**auth, "Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Type": "video/mp4",
                                    "X-Upload-Content-Length": str(video.stat().st_size)}, md)
            if st != 200 or not (hdr.get("Location") or hdr.get("location")):
                raise YouTubeError(f"could not start the upload (HTTP {st})", recoverable=st in (429, 500, 502, 503, 504))
            loc = hdr.get("Location") or hdr.get("location")
            st, resp, _ = transport("PUT", loc, {"Content-Type": "video/mp4"}, video.read_bytes(), 600)
            if st not in (200, 201):
                raise YouTubeError(f"upload failed (HTTP {st})", recoverable=st in (429, 500, 502, 503, 504))
            vid = json.loads(resp)["id"]
            if thumbnail and thumbnail.exists():
                st, _, _ = transport("POST", f"{THUMB_URL}?videoId={vid}", {**auth, "Content-Type": "image/jpeg"}, thumbnail.read_bytes())
                if st != 200:
                    log.warn("thumbnail upload failed; the video itself is uploaded", name="youtube", stage="publish")
            return vid
        except YouTubeError as e:
            last = e
            if not e.recoverable:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last = YouTubeError(f"network error: {type(e).__name__}", recoverable=True)
        sleep(2 ** attempt)
    raise last or YouTubeError("upload failed")


def publish_job(job_id: int, video: Path, thumbnail: Path | None, meta: dict, cfg: Config, index: int = 0, transport=http) -> dict:
    """Called by the Publishing Agent for a finished, QC-passed reel. Does nothing unless fully enabled."""
    s = status(cfg)
    if not cfg.AUTO_UPLOAD:
        db.set_upload(job_id, "skipped", detail="AUTO_UPLOAD=false")
        return {"status": "skipped", "reason": "AUTO_UPLOAD=false"}
    if not s["ready_to_upload"]:
        db.set_upload(job_id, "skipped", detail="no credentials / not authorised")
        return {"status": "skipped", "reason": "YouTube credentials are not configured"}
    if quota_used_today() + QUOTA_UPLOAD + QUOTA_THUMB > cfg.YOUTUBE_DAILY_QUOTA:
        db.set_upload(job_id, "deferred", detail="daily API quota would be exceeded")
        return {"status": "deferred", "reason": "daily quota"}
    when = datetime.now(timezone.utc) + timedelta(minutes=cfg.YOUTUBE_PUBLISH_DELAY_MIN * (index + 1))
    try:
        vid = upload(video, thumbnail, meta, cfg, when, transport)
    except YouTubeError as e:
        db.set_upload(job_id, "failed", detail=str(e))
        return {"status": "failed", "reason": str(e)}
    db.set_upload(job_id, "uploaded", video_id=vid, scheduled_at=when.isoformat(), detail="scheduled")
    return {"status": "uploaded", "video_id": vid, "scheduled_at": when.isoformat()}
