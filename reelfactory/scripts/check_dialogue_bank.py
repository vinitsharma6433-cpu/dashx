"""Quality gate for a dialogue story file (stories/dialogue_bank.md or a candidate file). A story is ACCEPTED only if it passes:

  format     4 scenes, 1-2 lines each, two different speakers when 2 lines, every speaker on stage, speaker is a cast name
  rules      DASHX rules, lines at most 14 words, Devanagari only, no narration tag (बोला / बोली / ने कहा ...), pop-up word in Hindi
  roles      bowler bowls, batter bats, only grown-ups catch (nothing silently repaired)
  presence   a character named inside a line is on stage in that scene
  hook       the first line has 4-8 words and ends with ! or ?
  punchline  the last line ends with ! or ? and does not just repeat the ending
  hook       one reel-specific Hindi hook (<= 60 chars, exactly 1 emoji, not a dialogue line, not the ending, different wording from every other hook)
  score      Story Quality Score >= 80 (originality against every reel made and every other accepted story)
  unique     no spoken line, ending or ending word repeated; the whole reel is short enough (spoken words <= 46)
and for the file: at most 6 of 30 stories end with a catch scene (limit scales with the number of stories checked).

    python scripts/check_dialogue_bank.py [file] [--max-catch 6] [--json out.json] [--only-new]
Exit code 1 if any story fails or the catch limit is broken.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import daily  # noqa: E402
from factory import story as sm  # noqa: E402

NAMES = {"सचिन": "sachin", "सूर्या": "surya", "दादाजी": "dadaji", "आंटी": "aunty", "पिंटू": "pintu", "गोलू": "golu", "मीना": "meena", "कोच": "coach", "ब्रूनो": "bruno"}
STOP = {"भी", "का", "की", "के", "में", "ही", "है", "रहा", "गई", "गया", "गए", "था", "थी", "हो", "सब"}
MAX_SPOKEN_WORDS = 46
args = [a for a in sys.argv[1:] if not a.startswith("--") and not a.endswith(".json") and not a.isdigit()]
file = Path(args[0]) if args else daily.DIALOGUE_BANK
daily.DIALOGUE_BANK = file
max_catch_30 = int(sys.argv[sys.argv.index("--max-catch") + 1]) if "--max-catch" in sys.argv else 6


def corpus_without(skip: set) -> dict:
    plots, titles, endings, lines = [], [], [], []
    for f in (ROOT / "reels").glob("*/script.json"):
        if f in skip:
            continue
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        plots.append(j.get("story", {}).get("plot", ""))
        titles.append(j.get("title", ""))
        endings.append(j.get("story", {}).get("closing", ""))
        lines += [x.get("voice", "") for x in j["scenes"][:-1]]
    return {"plots": [x for x in plots if x], "titles": titles, "endings": [x for x in endings if x], "lines": lines}


def main():
    stories = daily.parse_dialogue_bank()
    used = daily.History(daily.ms.USED)
    ref_all = sm.corpus()
    rendered = {}  # title -> script of a reel already rendered from that story: a story is not a duplicate of its own render
    for f in (ROOT / "reels").glob("*/script.json"):
        try:
            rendered.setdefault(json.loads(f.read_text(encoding="utf-8")).get("title"), []).append(f)
        except Exception:
            pass
    accepted_lines, accepted_end, accepted_plots, results = [], [], [], []
    accepted_hooks: list[str] = []
    catch_end = 0
    for i, b in enumerate(stories):
        ref = ref_all
        if b["title_hi"] in rendered:
            skip = set(rendered[b["title_hi"]])
            ref = corpus_without(skip)
        probs = []
        data = {"title_hi": b["title_hi"], "title_en": b["title_en"], "plot_en": b["plot_en"], "scenes": b["rows"], "closing_hi": b["closing"]}
        story, p = daily.from_dialogue_data(data)
        probs += p
        cast, score, words, last_t = [], None, 0, ""
        if story:
            probs += daily.story_problems(story, used, [], [])
            for row, sc in zip(b["rows"], story["scenes"]):
                pr = sc["params"]
                want = {"face-off": [pr.get("left"), pr.get("right")], "run-up": [pr.get("bowler"), pr.get("batter")], "shot": [pr.get("batter"), pr.get("watcher")], "catch": [pr.get("catcher"), pr.get("watchers", [None])[0]]}[sc["template"]]
                if [row["who_a"], row["who_b"]] != want:
                    probs.append(f"role repaired in a {sc['template']} scene: {row['who_a']},{row['who_b']} -> {want}")
                if sc["template"] == "catch" and row["board"] and row["board"] != pr["watchers"][1]:
                    probs.append(f"second watcher {row['board']!r} is not valid")
                present = daily.scene_cast(pr)
                for d in sc["dialogue"]:
                    for hi, en in NAMES.items():
                        if hi in d["line"] and en not in present:
                            probs.append(f"a line names {hi} but {en} is not in scene {sc['template']}")
            all_lines = [d["line"] for sc in story["scenes"] for d in sc["dialogue"]]
            words = sum(len(x.split()) for x in all_lines)
            if words > MAX_SPOKEN_WORDS:
                probs.append(f"{words} spoken words: too long for 25 s (max {MAX_SPOKEN_WORDS})")
            first, last = all_lines[0], all_lines[-1]
            if not (4 <= len(first.split()) <= 8 and re.search(r"[!?]", first)):
                probs.append("weak hook: first line should be 4-8 words with ! or ?")
            if not re.search(r"[!?]$", last):
                probs.append("the last line (punchline) should end with ! or ?")
            if sm.similarity(last, story["closing"]) > 0.6:
                probs.append("the ending only repeats the last line")
            sc_ = sm.score_story(story, ref={**ref, "plots": ref["plots"] + accepted_plots, "endings": ref["endings"] + accepted_end, "lines": ref["lines"] + accepted_lines})
            score = sc_["score"]
            if score < 80:
                probs.append(f"story score {score} < 80: {'; '.join(sc_['notes'])[:140]}")
            for ln in all_lines:
                if not ln.replace("भौं", "").strip(" !?") == "" and any(sm.similarity(ln, o) > 0.8 for o in accepted_lines):
                    probs.append(f"line repeats another story: {ln}")
            last_word = lambda t: t.split()[-1].strip("!?।,")
            if last_word(story["closing"]) not in STOP and any(last_word(story["closing"]) == last_word(e) for e in accepted_end):
                probs.append("ending ends on the same word as another ending: " + last_word(story["closing"]))
            if any(sm.similarity(story["closing"], e) > 0.6 for e in accepted_end):
                probs.append("ending too close to another ending")
            from factory import seo as seo_mod  # noqa: PLC0415
            hook = b.get("hook", "")
            probs += [f"hook: {x}" for x in seo_mod.hook_problems(hook, {"scenes": story["scenes"], "story": {"closing": story["closing"]}})]
            if hook and any(seo_mod.hooks_clash(hook, h) for h in accepted_hooks):
                probs.append("hook has nearly the same wording as another story's hook")
            cast = sorted(sm.cast_of(story))
            last_t = story["scenes"][-1]["template"]
        res = {"title": b["title_en"], "title_hi": b["title_hi"], "score": score, "cast": cast, "speakers": [], "last_line": "", "last_template": last_t, "words": words, "problems": probs}
        if story:
            seen = []
            for sc in story["scenes"]:
                for d in sc["dialogue"]:
                    if d["speaker"] not in seen:
                        seen.append(d["speaker"])
            res["speakers"], res["last_line"] = seen, story["scenes"][-1]["dialogue"][-1]["line"]
        results.append(res)
        if not probs:
            accepted_lines += [d["line"] for sc in story["scenes"] for d in sc["dialogue"]]
            accepted_end.append(story["closing"])
            accepted_plots.append(story["plot_en"])
            accepted_hooks.append(b.get("hook", ""))
        if last_t == "catch":
            catch_end += 1
    bad = [r for r in results if r["problems"]]
    for r in results:
        print(("OK   " if not r["problems"] else "FAIL ") + f"{r['title']:<26} score {r['score']}  words {r['words']}  last scene {r['last_template']}")
        for p in r["problems"]:
            print("       -", p)
    limit = max(1, round(max_catch_30 * len(stories) / 30)) if len(stories) != 30 else max_catch_30
    catch_ok = catch_end <= limit
    scores = [r["score"] for r in results if r["score"] is not None]
    print(f"\n{len(results) - len(bad)}/{len(results)} accepted, mean score {sum(scores) / max(1, len(scores)):.1f}; stories ending with a catch scene: {catch_end} (limit {limit}) {'OK' if catch_ok else 'TOO MANY'}")
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(1 if bad or not catch_ok else 0)


main()
