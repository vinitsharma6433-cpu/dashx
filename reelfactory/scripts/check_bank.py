"""Quality gate for stories/bank.md (or another bank file). A story is ACCEPTED only if it passes every gate:

  rules      DASHX rules, 2-8 word lines, 2-5 word ending, Devanagari only, 4 scenes, >=3 visuals
  roles      the builder had to repair no character role (bowler bowls, batter bats, only grown-ups catch, Bruno only watches)
  presence   a character named in a line is on stage in that scene (character consistency)
  hook       first line 4-8 words with ! or ?  (heuristic)
  score      Story Quality Score >= MIN_SCORE (originality is measured against every reel made AND every other bank story)
  unique     no spoken line, ending or plot repeats another story (no repeated punchline)

    python scripts/check_bank.py [bank-file] [--min 80] [--json out.json]
Exit code 1 if any story fails.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import daily  # noqa: E402
from factory import story as sm  # noqa: E402

NAMES = {"सचिन": "sachin", "सूर्या": "surya", "दादाजी": "dadaji", "आंटी": "aunty", "पिंटू": "pintu", "गोलू": "golu", "मीना": "meena", "कोच": "coach", "ब्रूनो": "bruno"}
args = [a for a in sys.argv[1:] if not a.startswith("--") and not a.endswith(".json") and not a.isdigit()]
bank_file = Path(args[0]) if args else daily.BANK
min_score = float(sys.argv[sys.argv.index("--min") + 1]) if "--min" in sys.argv else 80.0
if args:
    daily.BANK = bank_file


def scene_chars(sc: dict) -> set[str]:
    out = set()
    for v in sc["params"].values():
        out |= {x for x in (v if isinstance(v, list) else [v]) if x in daily.ROSTER}
    return out


def main():
    stories = daily.parse_bank()
    used = daily.History(daily.ms.USED)
    done = " ".join(used.recent_titles(1000))
    ref = sm.corpus()
    results, accepted_lines, accepted_end, accepted_plots = [], [], [], []
    for i, b in enumerate(stories):
        if b["title_hi"] in done or b["title_en"] in done:
            continue  # already produced: it is in the corpus
        probs = []
        data = {"title_hi": b["title_hi"], "title_en": b["title_en"], "plot_en": b["plot_en"], "scenes": b["rows"], "closing_hi": b["closing"]}
        story, p = daily.from_llm_data(data, seed=i, mins={})
        probs += p
        if story:
            probs += daily.story_problems(story, used, [], [])
            # roles repaired by the builder?
            for row, sc in zip(b["rows"], story["scenes"]):
                pr = sc["params"]
                want = {"face-off": [pr.get("left"), pr.get("right")], "run-up": [pr.get("bowler"), pr.get("batter")], "shot": [pr.get("batter"), pr.get("watcher")], "catch": [pr.get("catcher"), pr.get("watchers", [None])[0]]}[sc["template"]]
                if [row["who_a"], row["who_b"]] != want:
                    probs.append(f"role repaired in a {sc['template']} scene: {row['who_a']},{row['who_b']} -> {want}")
                present = scene_chars(sc)
                for hi, en in NAMES.items():
                    if hi in sc["line"] and en not in present:
                        probs.append(f"line names {hi} but {en} is not in that scene")
                if sc["template"] == "catch" and row["board"] and row["board"] != pr["watchers"][1]:
                    probs.append(f"second watcher {row['board']!r} is not valid")
            first = story["scenes"][0]["line"]
            if not (4 <= len(first.split()) <= 8 and re.search(r"[!?]", first)):
                probs.append("weak hook: first line should be 4-8 words with ! or ?")
            sc_ = sm.score_story(story, ref={**ref, "plots": ref["plots"] + accepted_plots, "endings": ref["endings"] + accepted_end, "lines": ref["lines"] + accepted_lines})
            if sc_["score"] < min_score:
                probs.append(f"story score {sc_['score']} < {min_score}: {'; '.join(sc_['notes'])[:140]}")
            lines = [s["line"] for s in story["scenes"]]
            for ln in lines:
                if any(sm.similarity(ln, o) > 0.8 for o in accepted_lines):
                    probs.append(f"line repeats another story: {ln}")
            STOP = {"भी", "का", "की", "के", "में", "ही", "है", "रहा", "गई", "गया", "गए", "था", "थी", "हो", "सब"}
            last = lambda t: t.split()[-1].strip("!?।,")
            if last(story["closing"]) not in STOP and any(last(story["closing"]) == last(e) for e in accepted_end):
                probs.append("ending ends on the same word as another ending: " + last(story["closing"]))
            if any(sm.similarity(story["closing"], e) > 0.6 for e in accepted_end):
                probs.append("ending too close to: " + max(accepted_end, key=lambda e: sm.similarity(story["closing"], e)))
            if any(sm.similarity(story["plot_en"], pl) > 0.6 for pl in accepted_plots):
                probs.append("plot too close to another story")
            cast = sorted(sm.cast_of(story))
        else:
            sc_, cast = {"score": None}, []
        res = {"title": b["title_en"], "score": sc_["score"], "cast": cast, "problems": probs}
        results.append(res)
        if not probs:
            accepted_lines += [s["line"] for s in story["scenes"]]
            accepted_end.append(story["closing"])
            accepted_plots.append(story["plot_en"])
    bad = [r for r in results if r["problems"]]
    for r in results:
        print(("OK   " if not r["problems"] else "FAIL ") + f"{r['title']:<28} score {r['score']}  {', '.join(r['cast'])}")
        for p in r["problems"]:
            print("       -", p)
    scores = [r["score"] for r in results if r["score"] is not None]
    print(f"\n{len(results) - len(bad)}/{len(results)} accepted, mean score {sum(scores) / max(1, len(scores)):.1f}")
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(1 if bad else 0)


main()
