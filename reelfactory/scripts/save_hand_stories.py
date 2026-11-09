"""Save hand-written DASHX stories (no LLM) in exactly the format make_stories.py produces.

    .venv\\Scripts\\python.exe scripts\\save_hand_stories.py

The stories below were written by the coding assistant. Each spoken line is plain Devanagari Hindi.
The DASHX brand line is NOT written here: make_stories.make_script() adds it to the last scene.
Every line is checked with story_rules.py before anything is saved.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import make_stories as ms  # noqa: E402  (reuses its format, duration estimate and file writing)
from story_rules import hindi_problems, rule_problems  # noqa: E402

# who_a / who_b follow make_stories.build_scenes():
#   face-off: left = a, right = b      run-up: bowler = a, batter = b
#   shot: batter = a, watcher = b      catch: catcher is always Dadaji, b = first watcher
STORIES = [
    {
        "title_hi": "चाय वाला कैच", "title_en": "Chai Wala Catch",
        "plot_en": "Surya swears he will get Sachin out today, Sachin smashes the ball sky-high, and Dadaji catches it without spilling his chai.",
        "scenes": [
            ("face-off", "surya", "sachin", "DARE", "सूर्या बोला, आज तुझे आउट करूँगा!"),
            ("run-up", "surya", "sachin", "", "सूर्या ने दौड़कर गेंद फेंकी।"),
            ("shot", "sachin", "surya", "", "सचिन ने गेंद आसमान में उड़ा दी!"),
            ("catch", "dadaji", "surya", "", "दादाजी ने चाय पीते-पीते कैच पकड़ा!"),
        ],
        "closing_hi": "गली क्रिकेट का मज़ा ही अलग!",
    },
    {
        "title_hi": "पहले मेरी बारी", "title_en": "My Turn First",
        "plot_en": "Both boys want to bat first; Sachin wins, hits it sky-high, and Dadaji catches it and announces that now he will bat.",
        "scenes": [
            ("face-off", "sachin", "surya", "MINE!", "सचिन बोला, पहले मैं बैटिंग करूँगा!"),
            ("run-up", "surya", "sachin", "", "सूर्या मुँह बनाकर गेंद लेकर दौड़ा।"),
            ("shot", "sachin", "surya", "", "सचिन का शॉट सीधा आसमान में!"),
            ("catch", "dadaji", "surya", "", "ऊपर से दादाजी ने गेंद लपक ली!"),
        ],
        "closing_hi": "अब बैटिंग दादाजी की!",
    },
    {
        "title_hi": "खिड़की बच गई", "title_en": "The Window Is Safe",
        "plot_en": "Sachin's big shot heads for the neighbour auntie's window and the boys panic, until Dadaji catches the ball just in time.",
        "scenes": [
            ("run-up", "surya", "sachin", "", "सूर्या ने ज़ोर से गेंद फेंकी।"),
            ("shot", "sachin", "surya", "", "सचिन ने गेंद ऊँची उठा दी!"),
            ("face-off", "sachin", "surya", "OOPS!", "अब आंटी की खिड़की की ख़ैर नहीं!"),
            ("catch", "dadaji", "sachin", "", "तभी दादाजी ने गेंद पकड़ ली!"),
        ],
        "closing_hi": "खिड़की भी बची, खेल भी!",
    },
    {
        "title_hi": "सूर्या का घमंड", "title_en": "Surya's Big Talk",
        "plot_en": "Surya boasts that nobody can play his bowling, Sachin sends the ball into the sky, and Surya is left speechless but still smiling.",
        "scenes": [
            ("face-off", "surya", "sachin", "SURE?", "सूर्या बोला, मेरी गेंद कोई नहीं खेलेगा!"),
            ("run-up", "surya", "sachin", "", "सूर्या पूरी ताक़त से दौड़ा।"),
            ("shot", "sachin", "surya", "", "सचिन ने गेंद आसमान में पहुँचा दी!"),
            ("face-off", "surya", "sachin", "WOW!", "सूर्या का मुँह खुला रह गया!"),
        ],
        "closing_hi": "फिर भी दोनों हँसते रहे!",
    },
    {
        "title_hi": "सोते हुए दादाजी", "title_en": "Dadaji Is Asleep",
        "plot_en": "The boys whisper so Dadaji can sleep, but Surya's shot flies straight at his chair, and Dadaji catches it in his sleep.",
        "scenes": [
            ("face-off", "sachin", "surya", "SHH!", "दादाजी सो रहे हैं, धीरे खेलना!"),
            ("run-up", "sachin", "surya", "", "सचिन दबे पाँव गेंद लेकर दौड़ा।"),
            ("shot", "surya", "sachin", "", "सूर्या का शॉट सीधा दादाजी की ओर!"),
            ("catch", "dadaji", "sachin", "", "दादाजी ने सोते-सोते कैच पकड़ लिया!"),
        ],
        "closing_hi": "दादाजी तो जादूगर निकले!",
    },
]


def as_llm_data(s: dict) -> dict:
    return {
        "title_hi": s["title_hi"], "title_en": s["title_en"], "plot_en": s["plot_en"],
        "scenes": [{"template": t, "who_a": a, "who_b": b, "board": bd, "line_hi": ln} for t, a, b, bd, ln in s["scenes"]],
        "closing_hi": s["closing_hi"],
    }


def main() -> int:
    mins = ms.template_minimums()
    history = ms.History(ms.USED)
    bad = 0
    prepared = []
    for k, s in enumerate(STORIES):
        scenes, problems = ms.build_scenes(as_llm_data(s), seed=k, mins=mins)
        problems += [f"title {p}" for p in hindi_problems(s["title_hi"], 1, 10)]
        problems += [f"title_en/plot_en {p}" for p in rule_problems(s["title_en"] + " " + s["plot_en"])]
        if problems:
            bad += 1
            print(f"{s['title_en']}: " + "; ".join(problems))
        prepared.append((s, scenes))
    if bad:
        print(f"{bad} story(ies) failed the checks; nothing saved.")
        return 1

    for s, scenes in prepared:
        lines = [x["line"] for x in scenes]
        durs = ms.estimate_durations(scenes, lines, mins)
        name = ms.unique_name(s["title_en"])
        script = ms.make_script(name, s["title_hi"], s["plot_en"], {"subject": s["title_en"]}, scenes, lines, durs, None, [], "none")
        script["story"]["writer"] = "written by the coding assistant (no LLM run)"
        script["story"]["doctor_score"] = None
        (ms.REELS / name).mkdir(parents=True, exist_ok=True)
        (ms.REELS / name / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        history.add_used(date.today().isoformat(), name, f"{s['title_hi']} ({s['title_en']})", s["plot_en"])
        print(f"saved reels/{name}/script.json  ({sum(durs):.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
