"""Story Refill reliability (retry once, native fallback on the same key, the real reason in the log), the tunable data files (prompt wording, hook vocabulary)
with the code staying protected, and the low-stock alert."""
import json
import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO / "autonomy"))
import alerts  # noqa: E402
import guard  # noqa: E402
import refill_bank as rb  # noqa: E402
import report  # noqa: E402
import story_rules as sr  # noqa: E402

IST = guard.IST
NOW = datetime(2026, 11, 14, 15, 30, tzinfo=IST)
MSG = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hello"}]


class Fake:
    """Replaces rb.http: a list of (code, text) answers, in order. Counts like the real one."""

    def __init__(self, answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, url, body, timeout, headers=None):
        rb.CALLS["n"] += 1
        self.calls.append((url, body, headers))
        return self.answers.pop(0)


OK = (200, json.dumps({"choices": [{"message": {"content": "STORY"}}]}))
NATIVE_OK = (200, json.dumps({"candidates": [{"content": {"parts": [{"text": "NATIVE STORY"}]}}]}))
NET = (0, "TimeoutError: The read operation timed out")


class Base(unittest.TestCase):
    def setUp(self):
        rb.CALLS.update(n=0, cap=12)
        rb.STATE.update(models=["m0", "m1", "m2", "m3"], idx=0, quota_hit=False, last_raw="", net_retried=False, native_tried=False)
        self.sleeps = []
        self._p = [mock.patch.object(rb, "SLEEP", lambda s: self.sleeps.append(s)), mock.patch.object(rb, "KEY", "k")]
        for p in self._p:
            p.start()

    def tearDown(self):
        for p in self._p:
            p.stop()


class Retry(Base):
    def test_one_network_failure_is_retried_once_after_a_backoff_on_the_same_model(self):
        f = Fake([NET, OK])
        with mock.patch.object(rb, "http", f):
            self.assertEqual(rb.ask(MSG), (200, "STORY"))
        self.assertEqual(self.sleeps, [rb.BACKOFF_S])
        self.assertEqual([c[1]["model"] for c in f.calls], ["m0", "m0"])
        self.assertEqual(rb.CALLS["n"], 2)

    def test_the_retry_happens_only_once_per_run(self):
        f = Fake([NET, NET, OK])
        with mock.patch.object(rb, "http", f):
            self.assertEqual(rb.ask(MSG), (200, "STORY"))
        self.assertEqual(self.sleeps, [rb.BACKOFF_S])
        self.assertEqual([c[1]["model"] for c in f.calls], ["m0", "m0", "m1"])

    def test_models_are_tried_in_turn_then_the_native_endpoint_once_with_the_same_key(self):
        f = Fake([NET, NET, NET, NET, NET, NATIVE_OK])
        with mock.patch.object(rb, "http", f):
            self.assertEqual(rb.ask(MSG), (200, "NATIVE STORY"))
        url, body, headers = f.calls[-1]
        self.assertIn(":generateContent", url)
        self.assertEqual(headers["x-goog-api-key"], "k")
        self.assertNotIn("Authorization", headers)
        self.assertEqual(body["systemInstruction"], {"parts": [{"text": "sys"}]})
        self.assertEqual(body["contents"], [{"role": "user", "parts": [{"text": "hello"}]}])
        self.assertEqual(rb.CALLS["n"], 6)
        self.assertLessEqual(rb.CALLS["n"], rb.CALLS["cap"])

    def test_native_is_tried_only_once_and_a_failure_ends_the_run_like_before(self):
        f = Fake([NET] * 6)
        with mock.patch.object(rb, "http", f):
            code, txt = rb.ask(MSG)
            self.assertEqual(code, 0)
            self.assertIn("TimeoutError", txt)
            self.assertEqual(rb.CALLS["n"], 6)

    def test_a_quota_answer_is_never_retried_and_never_goes_to_the_fallback(self):
        err = urllib.error.HTTPError("u", 429, "quota", {}, None)
        with mock.patch.object(rb.urllib.request, "urlopen", side_effect=err), mock.patch.object(err, "read", return_value=b'{"error":{"message":"quota"}}'):
            code, _ = rb.ask(MSG)
        self.assertEqual(code, 429)
        self.assertTrue(rb.STATE["quota_hit"])
        self.assertEqual(rb.CALLS["n"], 1)
        self.assertEqual(self.sleeps, [])

    def test_the_daily_call_cap_still_wins(self):
        rb.CALLS.update(n=11, cap=12)
        f = Fake([NET, NET, NET])
        with mock.patch.object(rb, "http", f):
            code, _ = rb.ask(MSG)
        self.assertLessEqual(rb.CALLS["n"], 12)
        self.assertEqual(rb.ask(MSG)[0], -1)

    def test_a_404_still_switches_model_without_a_retry_or_a_sleep(self):
        f = Fake([(404, "model not found"), OK])
        with mock.patch.object(rb, "http", f):
            self.assertEqual(rb.ask(MSG), (200, "STORY"))
        self.assertEqual(self.sleeps, [])
        self.assertEqual([c[1]["model"] for c in f.calls], ["m0", "m1"])

    def test_the_real_reason_of_a_network_failure_is_kept(self):
        with mock.patch.object(rb.urllib.request, "urlopen", side_effect=TimeoutError("The read operation timed out")):
            code, txt = rb.http("https://x", {}, 5)
        self.assertEqual(code, 0)
        self.assertEqual(txt, "TimeoutError: The read operation timed out")

    def test_the_stop_line_carries_the_reason(self):
        src = (ROOT / "scripts" / "refill_bank.py").read_text(encoding="utf-8")
        self.assertIn("Gemini answered HTTP {code}: stopped", src)
        self.assertIn("if code == 0 else", src)

    def test_the_story_checks_were_not_touched(self):
        src = (ROOT / "scripts" / "refill_bank.py").read_text(encoding="utf-8")
        for needle in ("MIN_JUDGE = 7", "MIN_MEERUT = 6", "MIN_TWIST = 6", "def check_block", "def judge", "FIXABLE_NOT"):
            self.assertIn(needle, src)


class PromptData(unittest.TestCase):
    SEED = {"situation": "x", "formula": {"name": "n", "pattern": "p", "example": "e"}}

    def with_file(self, text):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        p = Path(d.name) / "refill_prompt.json"
        if text is not None:
            p.write_text(text if isinstance(text, str) else json.dumps(text, ensure_ascii=False), encoding="utf-8")
        return mock.patch.object(rb, "PROMPT_FILE", p)

    def test_the_shipped_file_equals_the_built_in_wording(self):
        shipped = json.loads((ROOT / "stories" / "refill_prompt.json").read_text(encoding="utf-8"))
        self.assertEqual({k: shipped[k] for k in ("tone", "voice", "extras")}, rb.PROMPT_DEFAULT)
        self.assertEqual(rb.load_prompt_style(), rb.PROMPT_DEFAULT)

    def test_a_valid_change_reaches_the_prompt_and_the_fixed_rules_stay(self):
        new = {"tone": "Write natural everyday Hindi, short and playful, the way Meerut kids really talk.", "voice": "VOICE: give every character one fixed speech habit and keep it all the time.",
               "extras": ["Prefer a loud, physical conflict in the first scene."]}
        with self.with_file(new):
            msgs = rb.prompt_for(self.SEED, [], [], "normal", 1)
        sysmsg = msgs[0]["content"]
        self.assertIn("short and playful", sysmsg)
        self.assertIn("Prefer a loud, physical conflict", sysmsg)
        for fixed in ("COLD OPEN", "at most 34 spoken words", "exactly ONE emoji", "real TWIST", "Never mention price", "Put the field lines in this order", "Spell the names exactly"):
            self.assertIn(fixed, sysmsg)

    def test_every_kind_of_bad_file_falls_back_to_the_built_in_wording(self):
        good = {"tone": "Write natural everyday Hindi, short and playful, the way Meerut kids really talk.", "voice": "VOICE: give every character one fixed speech habit and keep it all the time.", "extras": []}
        bad = [None, "{not json", json.dumps([1]), {"tone": "x", "voice": "y"}, dict(good, tone="Mention the price and a big discount in every story, always."),
               dict(good, extras=["one extra line that is fine"] * 6), dict(good, voice="V" * 700), dict(good, extras=[5]), dict(good, extras=["Say DASHX in the first line of the story."])]
        for b in bad:
            with self.with_file(b):
                self.assertEqual(rb.load_prompt_style(), rb.PROMPT_DEFAULT, b)


class HookWords(unittest.TestCase):
    def setUp(self):
        self.saved = (sr._NAMES_HI, sr._THINGS_HI, sr._NUMBERS_HI, sr._STAKES_HI, sr._STAKE_STEMS, sr._ADDRESS_HI, sr._WEIGHTS)

    def tearDown(self):
        sr._NAMES_HI, sr._THINGS_HI, sr._NUMBERS_HI, sr._STAKES_HI, sr._STAKE_STEMS, sr._ADDRESS_HI, sr._WEIGHTS = self.saved

    def tmp(self, data):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        p = Path(d.name) / "hook_words.json"
        p.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return p

    def test_the_shipped_file_gives_exactly_the_built_in_score(self):
        line = "अबे मेरी गेंद कौन ले गया!"
        before = sr.hook_score(line)
        self.assertTrue(sr._apply_hook_words())
        self.assertEqual(sr.hook_score(line), before)
        self.assertEqual(sr._NAMES_HI, self.saved[0])
        self.assertEqual(sr._WEIGHTS, self.saved[6])

    def test_the_file_holds_only_the_log_only_hook_vocabulary(self):
        d = json.loads((ROOT / "stories" / "hook_words.json").read_text(encoding="utf-8"))
        self.assertEqual(set(d) - {"_about"}, {"names", "things", "numbers", "stakes", "stake_stems", "address", "weights"})
        text = json.dumps(d, ensure_ascii=False)
        for safety in ("_BAD_EN", "_BAD_HI", "_SENSITIVE", "_BAD_NAMES", "_JUNK", "_POLITE", "_BLAME", "price", "brand"):
            self.assertNotIn(safety, text)

    def test_a_tuned_file_changes_only_the_logged_score(self):
        d = json.loads((ROOT / "stories" / "hook_words.json").read_text(encoding="utf-8"))
        d["things"] = d["things"] + ["तरबूज"]
        self.assertTrue(sr._apply_hook_words(self.tmp(d)))
        self.assertIn("तरबूज", sr._THINGS_HI)

    def test_the_safety_checks_do_not_depend_on_the_file(self):
        bad_line = "इस गेंद की कीमत बहुत कम है"
        before = sr.line_problems(bad_line) if hasattr(sr, "line_problems") else sr._BAD_HI.search(bad_line) is not None
        d = json.loads((ROOT / "stories" / "hook_words.json").read_text(encoding="utf-8"))
        d["things"], d["stakes"] = ["कीमत"], ["कीमत"]
        sr._apply_hook_words(self.tmp(d))
        after = sr.line_problems(bad_line) if hasattr(sr, "line_problems") else sr._BAD_HI.search(bad_line) is not None
        self.assertEqual(before, after)
        self.assertIsNotNone(sr._BAD_HI.search(bad_line))

    def test_every_bad_file_keeps_the_built_in_lists(self):
        good = json.loads((ROOT / "stories" / "hook_words.json").read_text(encoding="utf-8"))
        bad = ["{broken", json.dumps({"names": []}), dict(good, names=[]), dict(good, things="x"), dict(good, weights={"LENGTH": 1}),
               dict(good, weights=dict(good["weights"], LENGTH=999)), dict(good, address=["x" * 40]), dict(good, stakes=list(range(3))), dict(good, weights={k: 0 for k in good["weights"]})]
        for b in bad:
            self.assertFalse(sr._apply_hook_words(self.tmp(b)), b)
            self.assertEqual(sr._NAMES_HI, self.saved[0])
            self.assertEqual(sr._WEIGHTS, self.saved[6])
        self.assertFalse(sr._apply_hook_words(Path("Z:/missing/hook_words.json")))


class Rules(unittest.TestCase):
    RULES = guard.load_rules()
    TUNABLE = ["reelfactory/stories/refill_prompt.json", "reelfactory/stories/hook_words.json"]

    def test_only_the_two_data_files_are_allowed_and_the_code_stays_protected(self):
        for p in self.TUNABLE:
            self.assertEqual(guard.classify(p, self.RULES)[0], "allow", p)
        for p in ("reelfactory/scripts/refill_bank.py", "reelfactory/scripts/story_rules.py", "reelfactory/stories/refill_usage.json", "reelfactory/stories/refill_daily.txt",
                  "reelfactory/stories/viral_formats.json", "reelfactory/scripts/check_dialogue_bank.py", "autonomy/RULES.json", "autonomy/TRUST_LADDER.md"):
            self.assertNotEqual(guard.classify(p, self.RULES)[0], "allow", p)
        for variant in ("REELFACTORY/stories/Refill_Prompt.json", "reelfactory\\stories\\refill_prompt.json", "reelfactory/stories/../scripts/refill_bank.py"):
            self.assertIn(guard.classify(variant, self.RULES)[0], ("allow", "extract", "deny"))
        self.assertNotEqual(guard.classify("reelfactory/stories/../scripts/refill_bank.py", self.RULES)[0], "allow")

    def test_the_same_limits_apply(self):
        lim = self.RULES["limits"]
        self.assertEqual((lim["max_self_changes_per_day"], lim["max_files_per_change"], lim["watch_window_reels"], lim["blocked_idea_days"]), (1, 3, 2, 14))
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ok_time, window = NOW, NOW.replace(hour=12, minute=0)
            self.assertTrue(guard.check_change(self.TUNABLE, ok_time, root, self.RULES).ok)
            self.assertFalse(guard.check_change(self.TUNABLE, window, root, self.RULES).ok)                           # blocked window
            self.assertFalse(guard.check_change(self.TUNABLE + ["reelfactory/stories/dialogue_bank.md", "reelfactory/stories/situations.json"], ok_time, root, self.RULES).ok)   # 4 files
            self.assertFalse(guard.check_change(self.TUNABLE + ["reelfactory/scripts/refill_bank.py"], ok_time, root, self.RULES).ok)       # the code is never allowed along
            guard.record_change(self.TUNABLE[:1], ok_time, "t", root)
            self.assertFalse(guard.check_change(self.TUNABLE[1:], ok_time + timedelta(hours=1), root, self.RULES).ok)          # 1 change a day

    def test_the_permanent_deny_list_is_untouched(self):
        for p in ("poster/queue.py", "reelfactory/factory/qc.py", "reelfactory/factory/youtube.py", "reelfactory/factory/queue.py", "reelfactory/queue_config.json", "reelfactory/voices.json",
                  ".github/workflows/dashx-poster.yml", "autonomy/guard.py", "autonomy/TRUST_LADDER.md"):
            self.assertEqual(guard.classify(p, self.RULES)[0], "deny", p)

    def test_the_improver_cannot_edit_them_before_step_2(self):
        import ladder
        self.assertEqual(ladder.current_step(Path(tempfile.mkdtemp())), 1)


class LowStock(unittest.TestCase):
    def sig(self, n):
        return alerts.Signals(NOW, [], refill_daily=f"Story refill 2026-11-14: {n} stories left in the bank, 0 added today, Gemini calls used 5/12 (Gemini answered HTTP 0: stopped)\n")

    def ids(self, n):
        return [p.id for p in alerts.detect(self.sig(n))]

    def test_thresholds(self):
        self.assertEqual(self.ids(18), [])
        self.assertEqual(self.ids(12), [])
        self.assertEqual(self.ids(11), ["STORY_BANK_LOW"])
        self.assertEqual(self.ids(6), ["STORY_BANK_LOW"])
        self.assertEqual(self.ids(5), ["STORY_BANK_CRITICAL"])
        self.assertEqual(self.ids(0), ["STORY_BANK_CRITICAL"])

    def test_critical_is_loud_and_never_promises_a_posting_change(self):
        p = alerts.detect(self.sig(4))[0]
        self.assertIn("BAHUT KAM", p.title)
        self.assertIn("schedule", p.what)
        self.assertNotIn("slow", (p.what + p.title).lower())
        self.assertEqual(alerts.level(self.sig(4), [p])[0], "red")

    def test_the_daily_report_shows_it(self):
        txt = report.build(self.sig(9))
        self.assertIn("LOW STOCK", txt)
        self.assertIn("9 stories left", txt)
        self.assertIn("Story bank kam ho raha hai", txt)
        self.assertIn("CRITICAL STOCK", report.build(self.sig(3)))
        self.assertNotIn("STOCK**", report.build(self.sig(20)))

    def test_no_poster_or_schedule_code_is_involved(self):
        for f in ("alerts.py", "report.py"):
            src = (REPO / "autonomy" / f).read_text(encoding="utf-8")
            for bad in ("queue_config", "gh workflow run", "/dispatches", "queue.py"):
                self.assertNotIn(bad, src, f)

    def test_the_existing_extra_refill_trigger_is_already_in_heal_and_unchanged(self):
        r = guard.load_rules()["healing"]
        self.assertEqual((r["low_bank_stories"], r["refill_min_calls_left"]), (6, 4))
        self.assertIn("dashx-story-refill.yml", r["may_dispatch"])


if __name__ == "__main__":
    unittest.main()
