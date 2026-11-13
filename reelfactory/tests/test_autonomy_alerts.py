"""Phase 7 tests: human-only alerts (autonomy/alerts.py), status, and the daily report (autonomy/report.py). No network."""
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "autonomy"))
import alerts as A  # noqa: E402
import guard as g  # noqa: E402
import report as R  # noqa: E402

RULES = g.load_rules()
NOW = datetime(2026, 11, 13, 21, 0, tzinfo=g.IST)
OKALL = {n: {"ok": True} for n in ("youtube", "instagram", "facebook")}


def post(title, hours_ago, results=None, notes=None, nets=("youtube", "instagram", "facebook")):
    return {"title": f"{title} DASHX", "when": (NOW - timedelta(hours=hours_ago)).isoformat(), "networks": list(nets),
            "results": results if results is not None else dict(OKALL), "notes": notes or {}, "status": "done"}


def sig(posts=None, **kw):
    base = dict(now=NOW, posts=posts or [], refill_daily="Story refill 2026-11-13: 21 stories left in the bank, 2 added today, Gemini calls used 5/12", usage={"day": "2026-11-13", "calls": 5, "cap": 12})
    base.update(kw)
    return A.Signals(**base)


def ids(s):
    return [p.id for p in A.detect(s)]


class FakeIssues:
    def __init__(self):
        self.items, self.n, self.comments = [], 0, []

    def open_alerts(self):
        return [i for i in self.items if i["state"] == "open"]

    def create(self, body):
        self.n += 1
        self.items.append({"number": self.n, "title": A.TITLE, "body": body, "state": "open"})
        return self.n

    def update(self, n, body):
        next(i for i in self.items if i["number"] == n)["body"] = body

    def comment(self, n, text):
        self.comments.append((n, text))

    def close(self, n):
        next(i for i in self.items if i["number"] == n)["state"] = "closed"


class Detect(unittest.TestCase):
    def test_healthy_is_quiet(self):
        self.assertEqual(ids(sig([post("a", 5), post("b", 20)])), [])

    def test_meta_token_expired(self):
        bad = dict(OKALL, facebook={"ok": False, "error": "Cannot call API for app (code 200)", "tries": 3})
        p = A.detect(sig([post("a", 5, bad)]))
        self.assertEqual([x.id for x in p], ["META_TOKEN"])
        steps = " ".join(p[0].steps)
        for must in ("META_PAGE_TOKEN", "Settings", "Secrets and variables", "Actions", "Meta Check"):
            self.assertIn(must, steps)
        self.assertIn("paste mat", steps)                       # never paste the token

    def test_both_meta_networks_make_one_problem(self):
        bad = dict(OKALL, facebook={"ok": False, "error": "token expired"}, instagram={"ok": False, "error": "OAuthException 190"})
        p = A.detect(sig([post("a", 5, bad)]))
        self.assertEqual(len(p), 1)
        self.assertIn("Facebook", p[0].evidence)
        self.assertIn("Instagram", p[0].evidence)

    def test_it_clears_when_the_newest_attempt_worked(self):
        bad = dict(OKALL, facebook={"ok": False, "error": "token expired"})
        self.assertEqual(ids(sig([post("old", 30, bad), post("new", 5)])), [])            # a newer good post: fixed
        self.assertEqual(ids(sig([post("old", 5, bad), post("new", 30)])), ["META_TOKEN"])  # the newest is the bad one

    def test_old_failures_are_ignored(self):
        bad = dict(OKALL, facebook={"ok": False, "error": "token expired"})
        self.assertEqual(ids(sig([post("old", 100, bad)])), [])
        self.assertEqual(ids(sig([post("future", -5, bad)])), [])                           # not due yet

    def test_skipped_and_errorless_failures_are_not_alerts(self):
        self.assertEqual(ids(sig([post("a", 5, dict(OKALL, facebook={"ok": False, "skipped_late": True, "error": "token"}))])), [])
        self.assertEqual(ids(sig([post("a", 5, dict(OKALL, facebook={"ok": False}))])), [])
        self.assertEqual(ids(sig([post("a", 5, dict(OKALL, facebook={"ok": False, "error": "Instagram container not finished after 10 minutes"}))])), [])   # not owner work

    def test_youtube_token(self):
        bad = dict(OKALL, youtube={"ok": False, "error": "google token error: invalid_grant - Bad Request"})
        p = A.detect(sig([post("a", 5, bad)]))
        self.assertEqual([x.id for x in p], ["YT_TOKEN"])
        for must in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
            self.assertIn(must, " ".join(p[0].steps))

    def test_account_flagged_beats_token(self):
        bad = dict(OKALL, instagram={"ok": False, "error": "Your account is restricted: action blocked (token)"})
        p = A.detect(sig([post("a", 5, bad)]))
        self.assertEqual([x.id for x in p], ["ACCOUNT_FLAGGED"])
        self.assertIn("STOP_POSTER", " ".join(p[0].steps))
        self.assertIn("kabhi khud nahi", " ".join(p[0].steps))                              # the machine never touches the kill switch

    def test_gemini_key(self):
        s = sig(refill_daily="Story refill 2026-11-13: 21 stories left in the bank, 0 added today, Gemini calls used 2/12 (Gemini answered HTTP 403: stopped)")
        p = A.detect(s)
        self.assertEqual([x.id for x in p], ["GEMINI_KEY"])
        self.assertIn("GEMINI_API_KEY", " ".join(p[0].steps))
        self.assertEqual(ids(sig(refill_daily="Story refill 2026-11-13: 21 stories left, 0 added today, Gemini calls used 11/12 (call limit reached)")), [])    # a normal limit is not a bad key
        self.assertEqual(ids(sig(refill_daily="Story refill 2026-11-13: 21 stories left, Gemini calls used 12/12 (Gemini quota answer: stopped for the day)")), [])
        self.assertEqual(ids(sig(refill_daily="Story refill 2026-11-01: 21 stories left, 0 added today, Gemini calls used 2/12 (Gemini answered HTTP 403: stopped)")), ["GEMINI_KEY"])  # silent 12 days
        self.assertEqual(ids(sig(refill_daily="")), [])                                      # no report at all yet: not an alert

    def test_rules_tampered_and_revert_stuck(self):
        self.assertEqual(ids(sig(rules_ok=False, rules_why="x")), ["RULES_TAMPERED"])
        self.assertEqual(ids(sig(watch={"status": "revert_failed", "idea": "situation:x", "files": ["a.json"]})), ["REVERT_STUCK"])
        self.assertEqual(ids(sig(watch={"status": "watching"})), [])

    def test_texts_are_hinglish_steps_without_secrets(self):
        bad = dict(OKALL, facebook={"ok": False, "error": "token SECRETVALUE123 expired", "tries": 3})
        body = A.render_body(A.detect(sig([post("a", 5, bad)])), NOW)
        self.assertIn("Kya karna hai", body)
        self.assertNotIn("SECRETVALUE123", body)                                            # the error text is never copied
        self.assertNotIn("access_token", body)
        self.assertIn("1. ", body)
        self.assertIn("apne aap band", body)


class Issue(unittest.TestCase):
    def probs(self, *kinds):
        out = []
        for k in kinds:
            res = {"META_TOKEN": dict(OKALL, facebook={"ok": False, "error": "token expired"}),
                   "YT_TOKEN": dict(OKALL, youtube={"ok": False, "error": "google token error: invalid_grant"})}[k]
            out += A.detect(sig([post(k, 5, res)]))
        return out

    def test_one_issue_no_duplicates_and_auto_close(self):
        api = FakeIssues()
        self.assertEqual(A.sync_issue(api, [], NOW), "none")
        self.assertEqual(A.sync_issue(api, self.probs("META_TOKEN"), NOW), "created")
        self.assertEqual(A.sync_issue(api, self.probs("META_TOKEN"), NOW + timedelta(minutes=30)), "unchanged")      # same problem: no new issue, no noise
        self.assertEqual(len(api.items), 1)
        self.assertEqual(A.sync_issue(api, self.probs("META_TOKEN", "YT_TOKEN"), NOW + timedelta(hours=1)), "updated")
        self.assertEqual(len(api.items), 1)
        self.assertIn("YouTube", api.items[0]["body"])
        self.assertEqual(A.sync_issue(api, [], NOW + timedelta(hours=2)), "closed")
        self.assertEqual(api.items[0]["state"], "closed")
        self.assertIn("Sab theek ho gaya", api.comments[-1][1])
        self.assertEqual(A.sync_issue(api, [], NOW + timedelta(hours=3)), "none")
        self.assertEqual(A.sync_issue(api, self.probs("YT_TOKEN"), NOW + timedelta(days=1)), "created")             # a new problem later: a new issue
        self.assertEqual(len(api.open_alerts()), 1)

    def test_extra_open_issues_are_closed(self):
        api = FakeIssues()
        for _ in range(3):
            api.create("old")
        A.sync_issue(api, self.probs("META_TOKEN"), NOW)
        self.assertEqual([i["number"] for i in api.open_alerts()], [1])
        self.assertEqual(sum(1 for c in api.comments if "Duplicate" in c[1]), 2)

    def test_title_is_exact(self):
        self.assertEqual(A.TITLE, "DASHX ALERT")


class Status(unittest.TestCase):
    def test_levels(self):
        self.assertEqual(A.level(sig([post("a", 5)]), [])[0], "green")
        self.assertEqual(A.level(sig([], stops=["STOP_POSTER"]), [])[0], "yellow")
        self.assertEqual(A.level(sig([], refill_daily="Story refill 2026-11-13: 4 stories left in the bank"), [])[0], "yellow")
        self.assertEqual(A.level(sig([], watch={"status": "watching", "idea": "x"}), [])[0], "yellow")
        self.assertEqual(A.level(sig([], learning={"availability": {"x": "DENIED (HTTP 400)"}}), [])[0], "yellow")
        self.assertEqual(A.level(sig([], log_text=f"- {(NOW - timedelta(days=1)).strftime('%Y-%m-%d %H:%M')} IST | improve | auto_revert | x | y\n"), [])[0], "yellow")
        bad = dict(OKALL, facebook={"ok": False, "error": "token expired"})
        probs = A.detect(sig([post("a", 5, bad)]))
        self.assertEqual(A.level(sig([post("a", 5, bad)]), probs)[0], "red")

    def test_status_json_has_the_trend_and_no_alert_details(self):
        s = sig([post("a", 5)], trends={"topics": [{"topic": "Bhai Dooj", "story_angle": "angle", "expires": "2026-11-14"}, {"topic": "Old", "expires": "2026-11-01"}]})
        j = A.status_json(s, [])
        self.assertEqual((j["level"], j["trend"]["topic"]), ("green", "Bhai Dooj"))
        self.assertIsNone(A.status_json(sig([]), [])["trend"])
        self.assertNotIn("steps", json.dumps(j))

    def test_status_is_not_rewritten_every_half_hour(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            j = A.status_json(sig([post("a", 5)]), [])
            A.write_status(root, j)
            first = (root / "autonomy/status.json").read_text(encoding="utf-8")
            A.write_status(root, dict(j, updated=(NOW + timedelta(minutes=30)).isoformat(timespec="minutes")))
            self.assertEqual((root / "autonomy/status.json").read_text(encoding="utf-8"), first)
            A.write_status(root, dict(j, updated=(NOW + timedelta(hours=3)).isoformat(timespec="minutes")))
            self.assertNotEqual((root / "autonomy/status.json").read_text(encoding="utf-8"), first)
            A.write_status(root, dict(j, level="red", updated=(NOW + timedelta(hours=3, minutes=5)).isoformat(timespec="minutes")))   # a real change is written at once
            self.assertIn('"red"', (root / "autonomy/status.json").read_text(encoding="utf-8"))


class Run(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "poster").mkdir()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_run_writes_status_and_syncs_the_issue(self):
        bad = dict(OKALL, facebook={"ok": False, "error": "token expired"})
        (self.root / "poster" / "queue.json").write_text(json.dumps({"posts": [post("a", 5, bad)]}), encoding="utf-8")
        (self.root / "autonomy").mkdir()
        (self.root / "autonomy/TRUST_LADDER.md").write_bytes((REPO / "autonomy/TRUST_LADDER.md").read_bytes())      # the sealed Trust Ladder file
        api = FakeIssues()
        out = A.run(self.root, NOW, api)
        self.assertEqual((out["problems"], out["issue"], out["level"]), (["META_TOKEN"], "created", "red"))
        self.assertEqual(json.loads((self.root / "autonomy/status.json").read_text(encoding="utf-8"))["level"], "red")
        self.assertEqual(sorted(p.name for p in (self.root / "autonomy").iterdir()), ["TRUST_LADDER.md", "log.md", "status.json"])       # + the ladder's start line

    def test_kill_switch_does_nothing(self):
        (self.root / "STOP_AUTONOMY").write_text("", encoding="utf-8")
        api = FakeIssues()
        self.assertEqual(A.run(self.root, NOW, api), {"halted": True})
        self.assertEqual(api.items, [])
        self.assertFalse((self.root / "autonomy").exists())

    def test_files_written_are_machine_notes(self):
        for rel in A.ALLOWED_OUT:
            self.assertEqual(g.classify(rel, RULES)[0], "state", rel)
        for code in ("autonomy/alerts.py", "autonomy/report.py"):
            self.assertEqual(g.classify(code, RULES)[0], "deny", code)

    def test_no_secret_is_read(self):
        src = (REPO / "autonomy" / "alerts.py").read_text(encoding="utf-8")        # the secret NAMES appear only inside the owner's steps, never read
        import re
        self.assertTrue(set(re.findall(r'os\.environ\.get\("(\w+)"', src)) <= {"GITHUB_REPOSITORY", "GITHUB_TOKEN"})     # only the job's own GitHub token
        self.assertIn('os.environ.get("GITHUB_TOKEN"', src)
        self.assertNotIn("os.environ", (REPO / "autonomy" / "report.py").read_text(encoding="utf-8"))


class Report(unittest.TestCase):
    def sig(self, **kw):
        res_fail = dict(OKALL, instagram={"ok": False, "error": "Instagram processing ERROR SECRETVALUE failed", "tries": 2})
        day = "2026-11-13"
        posts = [post("two-whistles-talk", 8.5, results={"youtube": {"ok": True}, "instagram": {"ok": True}, "facebook": {"ok": True, "scheduled": True}}),
                 post("dog-coaching", 0.5, results=res_fail),
                 post("tomorrow", -14, results={"youtube": {"ok": True, "scheduled": True}}),
                 post("yesterday", 30)]
        posts[2]["when"] = "2026-11-14T12:30:00+05:30"
        log = (f"- {day} 14:00 IST | fix | poster_redispatch | no poster run active for 33 min | dispatched\n"
               f"- {day} 15:30 IST | improve | merged | add the trend situation 'Bhai Dooj' | f6778729; watching\n"
               f"- {day} 16:00 IST | improve | auto_revert | situation:x: new failure | reverted\n"
               f"- {day} 12:00 IST | report | duplicate_guard | same media queued twice | not fixed\n"
               "- 2026-11-12 10:00 IST | fix | poster_redispatch | yesterday's fix | dispatched\n")
        learning = {"reels_with_data": 6, "need": 5, "enough_data": True, "availability": {"youtube_statistics": "ok", "instagram_counts": "DENIED (HTTP 400): owner must decide"},
                    "groups": {"format": {"shop": {"avg": 71.5, "n": 3}, "normal": {"avg": None, "n": 1}}, "hook_type": {"question": {"avg": 60, "n": 4}}}}
        trends = {"topics": [{"topic": "Bhai Dooj", "story_angle": "A brother and sister settle a cricket argument", "expires": "2026-11-14"}, {"topic": "Gully rules", "story_angle": "house rules", "expires": "2026-11-14"}, {"topic": "Third", "story_angle": "x", "expires": "2026-11-14"}]}
        base = dict(posts=posts, log_text=log, learning=learning, trends=trends, watch={"status": "watching", "idea": "situation:bhai_dooj_2026", "merged_at": "2026-11-13T15:30:00+05:30"},
                    refill_daily="Story refill 2026-11-13: 21 stories left in the bank, 2 added today, Gemini calls used 5/12", usage={"day": "2026-11-13", "calls": 5, "cap": 12})
        base.update(kw)
        return A.Signals(now=NOW, **base)

    def test_all_sections(self):
        t = R.build(self.sig())
        for h in ("## 2026-11-13", "### Reels today (3 networks)", "### Failures", "### Fixes the machine made", "### Self-changes (made / reverted)",
                  "### Trends used in the story prompt", "### What the learning loop found", "### Story bank and Gemini quota"):
            self.assertIn(h, t)

    def test_reels_and_networks(self):
        t = R.build(self.sig())
        self.assertIn("| two-whistles-talk | 12:30 | posted | posted | posted |", t)
        self.assertIn("| dog-coaching | 20:30 | posted | FAILED (processing) | posted |", t)
        self.assertNotIn("| tomorrow |", t)                    # not today
        self.assertNotIn("| yesterday |", t)
        self.assertIn("dog-coaching / instagram: FAILED (processing)", t)

    def test_a_post_still_missing_30_minutes_after_its_slot_is_listed_as_a_failure(self):
        s = self.sig(posts=[post("late-one", 0.75, results={"youtube": {"ok": True}, "facebook": {"ok": True}}), post("just-now", 0.2, results={"youtube": {"ok": True}, "facebook": {"ok": True}})])
        t = R.build(s)
        self.assertIn("late-one / instagram: not posted (late", t)
        self.assertNotIn("just-now / instagram", t)

    def test_error_text_is_never_copied(self):
        self.assertNotIn("SECRETVALUE", R.build(self.sig()))

    def test_only_todays_fixes_and_self_changes(self):
        t = R.build(self.sig())
        self.assertIn("poster_redispatch - no poster run active", t)
        self.assertNotIn("yesterday's fix", t)
        self.assertIn("merged - add the trend situation 'Bhai Dooj'", t)
        self.assertIn("auto_revert - situation:x", t)
        self.assertIn("Now watching: situation:bhai_dooj_2026", t)
        self.assertIn("(heal report) 12:00: duplicate_guard", t)

    def test_trends_learning_bank_quota(self):
        t = R.build(self.sig())
        self.assertIn("- Bhai Dooj:", t)
        self.assertIn("- Gully rules:", t)
        self.assertNotIn("- Third:", t)                        # only the two fed into the prompt
        self.assertIn("Steering: ON", t)
        self.assertIn("Best format: shop (average score 71.5, 3 reels)", t)
        self.assertIn("NEEDS YOUR DECISION", t)
        self.assertIn("Stories left: 21 = about 10 days at 2 reels a day", t)
        self.assertIn("Gemini calls used in this quota day: 5/12", t)

    def test_quota_of_an_old_day_counts_as_zero(self):
        t = R.build(self.sig(usage={"day": "2026-11-10", "calls": 11, "cap": 12}))
        self.assertIn("used in this quota day: 0/12", t)

    def test_empty_day_and_missing_files(self):
        t = R.build(A.Signals(now=NOW, posts=[]))
        self.assertIn("No reel was due today.", t)
        self.assertIn("None today.", t)
        self.assertIn("The learning loop has not run yet.", t)
        self.assertIn("unknown", t)

    def test_open_alerts_are_listed(self):
        bad = dict(OKALL, facebook={"ok": False, "error": "token expired"})
        t = R.build(self.sig(posts=[post("a", 5, bad)]))
        self.assertIn("### Open alerts", t)
        self.assertIn("RED", t)

    def test_file_keeps_14_days_newest_first_and_replaces_the_same_day(self):
        existing = ""
        for i in range(20, 0, -1):
            d = (NOW - timedelta(days=i)).strftime("%Y-%m-%d")
            existing = R.merge_into_file(existing, f"## {d}\nold {d}\n", d)
        self.assertEqual(existing.count("## 20"), 14)
        merged = R.merge_into_file(existing, "## 2026-11-13\nnew report\n", "2026-11-13")
        again = R.merge_into_file(merged, "## 2026-11-13\nnewer report\n", "2026-11-13")
        self.assertEqual(again.count("## 2026-11-13\n"), 1)
        self.assertIn("newer report", again)
        self.assertNotIn("new report\n", again.replace("newer report", ""))
        days = [l[3:] for l in again.splitlines() if l.startswith("## 20")]
        self.assertEqual(days, sorted(days, reverse=True))
        self.assertEqual(len(days), 14)
        self.assertTrue(again.startswith("# DASHX daily report"))

    def test_run_writes_only_the_report_and_respects_the_kill_switch(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "poster").mkdir()
            (root / "poster" / "queue.json").write_text(json.dumps({"posts": [post("a", 5)]}), encoding="utf-8")
            self.assertEqual(R.run(root, NOW), "2026-11-13")
            R.run(root, NOW + timedelta(minutes=30))
            txt = (root / "status" / "daily.md").read_text(encoding="utf-8")
            self.assertEqual(txt.count("## 2026-11-13\n"), 1)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ["poster", "status"])
            (root / "STOP_AUTONOMY").write_text("", encoding="utf-8")
            (root / "status" / "daily.md").unlink()
            self.assertEqual(R.run(root, NOW), "halted")
            self.assertFalse((root / "status" / "daily.md").exists())


class StatusPage(unittest.TestCase):
    def test_the_page_shows_the_autonomy_status_safely(self):
        html = (REPO / "status" / "index.html").read_text(encoding="utf-8")
        self.assertIn("../autonomy/status.json", html)
        self.assertIn('id="autolast"', html)
        i = html.index("function autonomy()")
        block = html[i:i + 1800]
        self.assertNotIn("innerHTML", block)                    # text only
        self.assertIn("textContent", block)
        for level in ("green", "yellow", "red"):
            self.assertIn(level, block)
        self.assertIn("today's trend", block)


if __name__ == "__main__":
    unittest.main()
