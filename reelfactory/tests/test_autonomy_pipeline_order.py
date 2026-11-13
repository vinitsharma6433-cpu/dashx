"""The series-order change in factory/pipeline.py, tested through the REAL StoryWriterAgent._bank with fake story data.
What it must do: a series episode waits for a lower episode that is also ready. What it must never do: break the old order when the series data is broken."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "reelfactory"))
sys.path.insert(0, str(REPO / "autonomy"))
from factory import pipeline  # noqa: E402

REAL = object()          # "use the real series_memory module"


def block(title, series="", ep="", hook="h"):
    return {"title_en": title, "title_hi": f"hi-{title}", "plot_en": "p", "rows": [], "closing": f"end-{title}", "hook": hook, "card": "", "series": series, "ep": ep}


class Hist:
    def recent_titles(self, n):
        return []


def pick(blocks, scores, skip=(), series_module=REAL):
    """Run the real _bank with fake story data. `scores` = title -> story score. The OLD ranking = highest score first.
    series_module: REAL = the real module, None = the import failed (module missing), or any stand-in object."""
    mgr = SimpleNamespace(history=Hist(), batch_titles=[], batch_casts=[], cfg=SimpleNamespace(ALLOW_NARRATION=False, MIN_STORY_SCORE=0), mins={}, closings=[], ref={})
    agent = pipeline.StoryWriterAgent.__new__(pipeline.StoryWriterAgent)
    agent.m = mgr

    def builder(data, i, mins):
        if data["title_en"] in skip:
            return None, ["fails the quality checks"]
        return {"scenes": [{"line": "opening " + data["title_en"]}], "t": data["title_en"]}, []

    mod = pipeline.series_memory if series_module is REAL else series_module
    with mock.patch.object(pipeline.daily, "parse_dialogue_bank", lambda: blocks), \
            mock.patch.object(pipeline.daily, "from_dialogue_data", builder), \
            mock.patch.object(pipeline.daily, "story_problems", lambda *a, **k: []), \
            mock.patch.object(pipeline.daily, "recent_cast", lambda *a, **k: set()), \
            mock.patch.object(pipeline.story_mod, "score_story", lambda st, ref=None: {"score": scores[st["t"]], "notes": ""}), \
            mock.patch.object(pipeline.story_mod, "cast_of", lambda st: set()), \
            mock.patch.object(pipeline, "series_memory", mod):
        out = agent._bank({"usage": {}, "season_word": ""}, [])
    return out[0]["t"] if out else None


BRUNO = [block("Bruno Two", "Bruno Files", "2"), block("Bruno One", "Bruno Files", "1"), block("Bruno Three", "Bruno Files", "3"), block("Plain Story")]
SCORES = {"Bruno One": 80, "Bruno Two": 95, "Bruno Three": 90, "Plain Story": 70}


class SeriesOrder(unittest.TestCase):
    def test_the_hook_is_really_loaded(self):
        self.assertIsNotNone(pipeline.series_memory)

    def test_without_the_change_the_best_scoring_episode_would_go_out_of_order(self):
        self.assertEqual(pick(BRUNO, SCORES, series_module=None), "Bruno Two")          # the old behaviour: highest score, no order

    def test_episode_one_goes_first_although_episode_two_scores_higher(self):
        self.assertEqual(pick(BRUNO, SCORES), "Bruno One")

    def test_a_plain_story_is_not_held_back_by_a_series(self):
        self.assertEqual(pick(BRUNO, dict(SCORES, **{"Plain Story": 99})), "Plain Story")

    def test_a_lower_episode_that_fails_the_checks_never_blocks_the_next(self):
        self.assertEqual(pick(BRUNO, SCORES, skip=("Bruno One",)), "Bruno Two")

    def test_after_episode_one_is_used_episode_two_is_next(self):
        self.assertEqual(pick([b for b in BRUNO if b["title_en"] != "Bruno One"], SCORES), "Bruno Two")


class FailSafe(unittest.TestCase):
    """If the series data or the series code is broken, the OLD order must be used and nothing may raise."""

    def test_module_missing_gives_the_old_order(self):
        self.assertEqual(pick(BRUNO, SCORES, series_module=None), "Bruno Two")

    def test_in_order_raising_gives_the_old_order(self):
        class Boom:
            penalty = staticmethod(lambda *a, **k: 0)

            @staticmethod
            def in_order(*a, **k):
                raise RuntimeError("broken series code")
        self.assertEqual(pick(BRUNO, SCORES, series_module=Boom), "Bruno Two")

    def test_in_order_returning_nonsense_gives_the_old_order(self):
        for bad in (None, [], "x", 5):
            class Bad:
                penalty = staticmethod(lambda *a, **k: 0)
                in_order = staticmethod(lambda cands, _b=bad: _b)
            self.assertEqual(pick(BRUNO, SCORES, series_module=Bad), "Bruno Two", repr(bad))

    def test_penalty_raising_never_breaks_the_pick(self):
        class Boom:
            @staticmethod
            def penalty(*a, **k):
                raise RuntimeError("broken")
            in_order = staticmethod(lambda cands: cands)
        self.assertEqual(pick(BRUNO, SCORES, series_module=Boom), "Bruno Two")

    def test_half_imported_module_gives_the_old_order(self):
        class Half:                                   # attributes exist but are not callable
            penalty = None
            in_order = None
        self.assertEqual(pick(BRUNO, SCORES, series_module=Half), "Bruno Two")

    def test_broken_series_fields_in_the_bank_use_the_old_order(self):
        broken = [block("Bruno Two", "Bruno Files", "two"), block("Bruno One", "Bruno Files", ""), block("Bruno Three", None, None), block("Plain Story", "Bruno Files", "x")]
        self.assertEqual(pick(broken, SCORES), "Bruno Two")                       # nothing could be ordered: highest score, exactly as before

    def test_a_missing_memory_file_changes_nothing(self):
        import series_memory
        with mock.patch.object(series_memory, "ROOT", Path("Z:/does-not-exist")):
            self.assertEqual(series_memory.penalty("a", "b", "c"), 0)
        self.assertEqual(pick([block("A"), block("B")], {"A": 60, "B": 90}), "B")      # no series at all: the plain old ranking

    def test_the_real_import_guard_is_in_place(self):
        src = (REPO / "reelfactory" / "factory" / "pipeline.py").read_text(encoding="utf-8")
        self.assertIn("except Exception:\n    series_memory = None", src.replace("\r\n", "\n"))     # import failure = feature off
        self.assertIn("ordered = series_memory.in_order(cands)", src)
        self.assertIn("isinstance(ordered, list) and ordered", src)


if __name__ == "__main__":
    unittest.main()
