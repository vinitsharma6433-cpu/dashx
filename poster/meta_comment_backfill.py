"""One-off: post the first comment (buy links) on the two TEST reels that are already live. Creates no post.
Uses the ids saved in queue.json notes. Skips a comment that is already marked ok. Never prints the token."""
import json, os, sys
import requests
sys.path.insert(0, os.path.dirname(__file__))
import poster as P

def main():
    tok = os.environ.get("META_PAGE_TOKEN", "").strip()
    if not tok: print("::error::META_PAGE_TOKEN missing"); return 1
    q = json.load(open(P.QUEUE, encoding="utf-8"))
    p = next(e for e in q["posts"] if e["title"].startswith("META TEST"))
    notes = p.setdefault("notes", {})
    bad = False
    for key, idkey in (("ig", "ig_media_id"), ("fb", "fb_video_id")):
        if notes.get(key + "_comment") == ["ok"]:
            print(key, "comment already ok, skipped"); continue
        notes.pop(key + "_comment", None)
        P.meta_comments(p, notes[idkey], tok, key)
        print(key, "comment:", notes[key + "_comment"])
        bad = bad or notes[key + "_comment"] != ["ok"]
    json.dump(q, open(P.QUEUE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
