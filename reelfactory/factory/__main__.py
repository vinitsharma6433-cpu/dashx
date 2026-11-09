"""Command line:  python -m factory <command>      (npm run daily -- 5 --source bank  =  daily 5 --source bank)"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import backup, db, log, ops, youtube
from .config import load


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="factory", description="DASHX Autonomous Reel Factory")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("daily", help="make the day's reels (default 5)")
    d.add_argument("count", nargs="?", type=int)
    d.add_argument("--source", choices=["auto", "bank", "gemma"])
    d.add_argument("--force", action="store_true", help="make N MORE reels even if today's target is already met")
    s = sub.add_parser("schedule", help="run the daily scheduler")
    s.add_argument("--once", action="store_true")
    w = sub.add_parser("dashboard", help="local control centre")
    w.add_argument("--port", type=int, default=8765)
    sub.add_parser("status")
    b = sub.add_parser("backup")
    b.add_argument("label", nargs="?", default="manual")
    sub.add_parser("backups")
    r = sub.add_parser("restore")
    r.add_argument("zip")
    sub.add_parser("cleanup")
    q = sub.add_parser("queue", help="queue eligible ready reels in the dashx poster (poster/queue.json) and push")
    q.add_argument("--dry-run", action="store_true", help="show what would be queued, change nothing")
    q.add_argument("--no-push", action="store_true", help="commit locally, do not push")
    sub.add_parser("youtube-auth")
    sub.add_parser("youtube-status")
    rt = sub.add_parser("retry")
    rt.add_argument("job_id", type=int)
    f = sub.add_parser("feedback")
    f.add_argument("job_id", type=int)
    f.add_argument("rating", type=int)
    f.add_argument("note", nargs="?", default="")
    a = ap.parse_args(argv)

    if a.cmd == "daily":
        from .pipeline import ProductionManager
        cfg = load({"SOURCE": a.source} if a.source else None)
        out = ProductionManager(cfg).run_day(a.count, a.force)
        print(json.dumps({k: v for k, v in out.items() if k != "results"}, ensure_ascii=False))
        for r in out.get("results", []):
            print(f"  {r['status']:9} {r['name']:28} QC {r.get('qc', '-')} SEO {r.get('seo', '-')} story {r.get('story', '-')} repairs {r.get('repairs', 0)}")
        return 0 if out.get("status") in ("done",) else 1
    if a.cmd == "queue":
        from . import queue as queue_mod
        out = queue_mod.run(dry_run=a.dry_run, push=not a.no_push)
        print(out.note or "")
        print(f"queued {len(out.queued)}, not queued (checks failed) {len(out.blocked)}, already queued {len(out.skipped)}, older narration reels ignored {out.old_format}, pushed {out.pushed}")
        for e in out.queued:
            print(f"  + {e['title']}  {e['when']}  {e['yt_title']}\n" + "\n".join("      | " + ln for ln in e["captions"]["instagram"].split("\n")))
        for name, why in out.blocked:
            print(f"  - {name}: {'; '.join(why)}")
        if os.environ.get("DASHX_CI") and (out.blocked or (out.queued and not a.dry_run and not out.pushed)):
            return 2  # cloud run: a reel failed a check or could not be pushed, so the job must go red
        return 0
    if a.cmd == "schedule":
        from . import scheduler
        if a.once:
            print(scheduler.check_once() or "nothing due")
        else:
            scheduler.loop()
    elif a.cmd == "dashboard":
        from .dashboard import serve
        serve(a.port)
    elif a.cmd == "status":
        print(json.dumps({"config": load().public(), "stats": db.stats(), "lock": ops.lock_info(), "disk": ops.disk(), "youtube": youtube.status(load())}, indent=1))
    elif a.cmd == "backup":
        print(backup.create(a.label))
    elif a.cmd == "backups":
        print("\n".join(str(p) for p in backup.listing()) or "no backups yet")
    elif a.cmd == "restore":
        print("restored into (live files untouched):", backup.restore(a.zip))
    elif a.cmd == "cleanup":
        print(ops.cleanup())
    elif a.cmd == "youtube-auth":
        youtube.authorise()
    elif a.cmd == "youtube-status":
        print(json.dumps(youtube.status(load()), indent=1))
    elif a.cmd == "retry":
        from .pipeline import ProductionManager
        print(ProductionManager().retry(a.job_id))
    elif a.cmd == "feedback":
        db.add_feedback(a.job_id, a.rating, a.note)
        print("saved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
