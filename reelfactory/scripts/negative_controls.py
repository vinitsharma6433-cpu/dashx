"""Negative controls for the QC: build deliberately broken copies of a good reel and check that QC fails them (and that the
unchanged copy and every real reel still pass). Prints a confusion table; exit code 1 on any false PASS / false FAIL.

    python scripts/negative_controls.py [base-reel] [--json out.json]
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from factory import qc  # noqa: E402

FF = qc.FFMPEG
base = next((a for a in sys.argv[1:] if not a.startswith("--") and not a.endswith(".json")), "pintu-s-whistle")
SRC = ROOT / "output" / "reels" / f"{base}.mp4"
OUT = ROOT / "output" / "reels"


def ff(*args):
    r = subprocess.run([FF, "-v", "error", "-y", *args], capture_output=True)
    if r.returncode:
        raise RuntimeError(r.stderr.decode("utf-8", "replace")[-300:])


def dur():
    return float(json.loads(subprocess.run([qc.FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(SRC)], capture_output=True).stdout)["format"]["duration"])


D = dur()


def script_edit(fn):
    def w(name):
        p = ROOT / "reels" / name / "script.json"
        sc = json.loads(p.read_text(encoding="utf-8"))
        fn(sc)
        p.write_text(json.dumps(sc, ensure_ascii=False), encoding="utf-8")
    return w


def lone(sc):
    sc["scenes"][1]["subtitle"] = "हर बार गेंद ठीक सामने आती है बहुत"
    sc["scenes"][1]["subtitleWidth"] = 380


def drop_end(sc):
    sc["scenes"].pop()


def corrupt(dst):
    data = SRC.read_bytes()
    dst.write_bytes(data[: len(data) // 3])


# name, expected ("PASS"/"FAIL"), expected failing check ids (any of), how to build the mp4, optional script edit
CASES = [
    ("valid_copy", "PASS", [], lambda d: ff("-i", str(SRC), "-c", "copy", str(d)), None),
    ("valid_reencode", "PASS", [], lambda d: ff("-i", str(SRC), "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "192k", str(d)), None),
    ("missing_audio", "FAIL", ["audio_present"], lambda d: ff("-i", str(SRC), "-an", "-c:v", "copy", str(d)), None),
    ("silent_audio", "FAIL", ["audio_present"], lambda d: ff("-i", str(SRC), "-af", "volume=0", "-c:v", "copy", str(d)), None),
    ("clipped_audio", "FAIL", ["no_clipping", "loudness"], lambda d: ff("-i", str(SRC), "-af", "volume=24dB,alimiter=limit=1:level=disabled", "-c:v", "copy", str(d)), None),
    ("black_first_frame", "FAIL", ["first_frame"], lambda d: ff("-i", str(SRC), "-vf", "fade=t=in:st=0:d=0.8", "-c:a", "copy", str(d)), None),
    ("black_middle", "FAIL", ["black_or_frozen"], lambda d: ff("-i", str(SRC), "-vf", "drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='between(t,6,8)'", "-c:a", "copy", str(d)), None),
    ("frozen_frame", "FAIL", ["black_or_frozen"], lambda d: ff("-i", str(SRC), "-vf", "loop=loop=150:size=1:start=90", "-t", str(D), "-c:a", "copy", str(d)), None),
    ("too_short", "FAIL", ["duration"], lambda d: ff("-i", str(SRC), "-t", "15", "-c", "copy", str(d)), None),
    ("too_long", "FAIL", ["duration"], lambda d: ff("-i", str(SRC), "-vf", "tpad=stop_mode=clone:stop_duration=6", "-af", "apad", "-t", str(D + 6), str(d)), None),
    ("wrong_dimension", "FAIL", ["resolution"], lambda d: ff("-i", str(SRC), "-vf", "scale=720:1280", "-c:a", "copy", str(d)), None),
    ("wrong_fps", "FAIL", ["frame_rate"], lambda d: ff("-i", str(SRC), "-r", "24", "-c:a", "copy", str(d)), None),
    ("missing_end_card_scene", "FAIL", ["end_card"], lambda d: shutil.copy2(SRC, d), script_edit(drop_end)),
    ("end_card_logo_removed", "FAIL", ["logo_visible"], lambda d: ff("-i", str(SRC), "-vf", f"drawbox=x=0:y=0:w=iw:h=ih:color=gray:t=fill:enable='gte(t,{D - 4.5})'", "-c:a", "copy", str(d)), None),
    ("broken_subtitle_lone_word", "FAIL", ["subtitle_no_lone_word"], lambda d: shutil.copy2(SRC, d), script_edit(lone)),
    ("corrupted_mp4", "FAIL", ["file_readable"], corrupt, None),
    ("zero_byte_mp4", "FAIL", ["file_readable"], lambda d: d.write_bytes(b""), None),
]


def run_case(name, want, ids, build, edit):
    nm = f"_nc_{name}"
    rd = ROOT / "reels" / nm
    mp4 = OUT / f"{nm}.mp4"
    try:
        shutil.rmtree(rd, ignore_errors=True)
        shutil.copytree(ROOT / "reels" / base, rd)
        if edit:
            edit(nm)
        build(mp4)
        res = qc.inspect(nm)
        got = "PASS" if (res["passed"] and res["score"] >= 90) else "FAIL"
        failed = [c["id"] for c in res["failed"]]
        right_reason = want == "PASS" or any(i in failed for i in ids)
        return {"case": name, "expected": want, "got": got, "score": res["score"], "failed_checks": failed, "reason_ok": right_reason,
                "verdict": ("correct" if got == want and right_reason else "FALSE PASS" if got == "PASS" else "FALSE FAIL" if want == "PASS" else "wrong reason")}
    except Exception as e:  # a crash inside QC is itself a defect
        return {"case": name, "expected": want, "got": f"CRASH {type(e).__name__}: {e}"[:150], "score": None, "failed_checks": [], "reason_ok": False, "verdict": "QC CRASH"}
    finally:
        shutil.rmtree(rd, ignore_errors=True)
        mp4.unlink(missing_ok=True)


def main():
    rows = [run_case(*c) for c in CASES]
    # every real reel in output/ready must pass the same QC
    for f in sorted((ROOT / "output" / "ready").glob("*/*.mp4")):
        n = f.stem
        if (ROOT / "reels" / n / "script.json").exists() and (OUT / f"{n}.mp4").exists() and not n.startswith("_nc_"):
            r = qc.inspect(n)
            got = "PASS" if (r["passed"] and r["score"] >= 90) else "FAIL"
            rows.append({"case": f"real:{n}", "expected": "PASS", "got": got, "score": r["score"], "failed_checks": [c["id"] for c in r["failed"]], "reason_ok": True,
                         "verdict": "correct" if got == "PASS" else "FALSE FAIL"})
    for r in rows:
        print(f"{r['verdict']:<12} {r['case']:<32} expected {r['expected']} got {r['got']} score {r['score']} failed {r['failed_checks']}")
    bad = [r for r in rows if r["verdict"] != "correct"]
    print(f"\n{len(rows) - len(bad)}/{len(rows)} correct; false PASS {sum(r['verdict'] == 'FALSE PASS' for r in rows)}, false FAIL {sum(r['verdict'] == 'FALSE FAIL' for r in rows)}, other {sum(r['verdict'] in ('wrong reason', 'QC CRASH') for r in rows)}")
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(1 if bad else 0)


main()
