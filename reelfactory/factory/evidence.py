"""Repair evidence. A repair is called SUCCESSFUL only when independent media measurements (plain ffprobe/ffmpeg
commands, not the QC module) prove that the original defect is gone from the repaired file. Application logs and
database status are never enough.

    evidence/<job-id>/
        original_failed.mp4      copy of the failed video, taken BEFORE any repair (never overwritten)
        original_hash.txt        sha256 of that copy
        original_qc.json         the QC report that failed it
        repaired.mp4             the video after the repair attempts (kept even if the repair failed)
        repaired_hash.txt
        repaired_qc.json
        repair_log.json          every attempt: plan, parameters, timestamps, outcome, final verdict
        comparison_report.md     before/after independent measurements and the verdict
        after_repairN_failed.mp4  video that still failed after repair attempt N (extra evidence)

The evidence folder is protected: nothing in this project deletes it.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from . import ROOT, find_tool

EVIDENCE = ROOT / "evidence"
FFMPEG = find_tool("ffmpeg")
FFPROBE = find_tool("ffprobe")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _run(args: list[str]) -> str:
    r = subprocess.run(args, capture_output=True, timeout=300)
    return (r.stdout + b"\n" + r.stderr).decode("utf-8", "replace")


def _yavg(path: Path, t: float) -> float | None:
    out = _run([FFMPEG, "-hide_banner", "-nostats", "-ss", f"{t}", "-i", str(path), "-frames:v", "1", "-vf", "signalstats,metadata=print:file=-", "-f", "null", "-"])
    m = re.search(r"lavfi\.signalstats\.YAVG=([\d.]+)", out)
    return float(m.group(1)) if m else None


def measure(path: Path) -> dict:
    """Independent measurements of one video file (ffprobe + ffmpeg filters)."""
    raw = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels", "-of", "json", str(path)], capture_output=True).stdout
    pr = json.loads(raw or b"{}")
    streams = pr.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    a = next((s for s in streams if s.get("codec_type") == "audio"), {})
    vf = _run([FFMPEG, "-hide_banner", "-nostats", "-i", str(path), "-vf", "blackdetect=d=0.2:pix_th=0.10,freezedetect=n=-55dB:d=1.5", "-an", "-f", "null", "-"])
    af = _run([FFMPEG, "-hide_banner", "-nostats", "-i", str(path), "-af", "volumedetect,ebur128=peak=true", "-vn", "-f", "null", "-"])
    mean = re.search(r"mean_volume:\s*(-?[\d.]+)", af)
    peak = re.search(r"max_volume:\s*(-?[\d.]+)", af)
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", af)
    dur = float(pr.get("format", {}).get("duration", 0) or 0)
    return {
        "sha256": sha256(path), "bytes": path.stat().st_size, "duration_s": round(dur, 3), "width": v.get("width"), "height": v.get("height"),
        "fps": v.get("r_frame_rate"), "video_codec": v.get("codec_name"), "audio_codec": a.get("codec_name"), "has_audio": bool(a),
        "frame0_brightness": _yavg(path, 0.0), "frame_0_5s_brightness": _yavg(path, 0.5),
        "black_segments": [float(x) for x in re.findall(r"black_duration:([\d.]+)", vf)],
        "freeze_segments": [(float(s), float(d)) for s, d in zip(re.findall(r"freeze_start: ([\d.]+)", vf), re.findall(r"freeze_duration: ([\d.]+)", vf))],
        "mean_volume_db": float(mean.group(1)) if mean else None, "max_volume_db": float(peak.group(1)) if peak else None,
        "loudness_lufs": float(lufs[-1]) if lufs else None,
    }


def retest(check_id: str, m: dict) -> tuple[str, str]:
    """Re-test ONE originally failed check on measurements from `measure()`. status: pass | fail | unverified."""
    if check_id == "first_frame":
        a, b = m["frame0_brightness"], m["frame_0_5s_brightness"]
        return ("pass" if a is not None and b is not None and a >= 40 and b >= 40 else "fail"), f"frame 0 brightness {a}, 0.5 s {b} (need >= 40)"
    if check_id == "black_or_frozen":
        end = m["duration_s"] - 4.5
        bad = [f for f in m["freeze_segments"] if f[0] < end]
        return ("pass" if not m["black_segments"] and not bad else "fail"), f"black {m['black_segments']}, freeze before end card {bad}"
    if check_id == "duration":
        return ("pass" if 20.0 <= m["duration_s"] <= 25.2 else "fail"), f"{m['duration_s']} s"
    if check_id == "resolution":
        return ("pass" if (m["width"], m["height"]) == (1080, 1920) else "fail"), f"{m['width']}x{m['height']}"
    if check_id == "frame_rate":
        return ("pass" if m["fps"] == "30/1" else "fail"), f"{m['fps']}"
    if check_id == "audio_present":
        return ("pass" if m["has_audio"] and (m["mean_volume_db"] or -99) > -50 else "fail"), f"audio={m['has_audio']}, mean {m['mean_volume_db']} dB"
    if check_id == "no_clipping":
        return ("pass" if m["max_volume_db"] is not None and m["max_volume_db"] < -0.3 else "fail"), f"peak {m['max_volume_db']} dB"
    if check_id == "loudness":
        return ("pass" if m["loudness_lufs"] is not None and -19 <= m["loudness_lufs"] <= -13 else "fail"), f"{m['loudness_lufs']} LUFS"
    return "unverified", "no independent ffprobe/ffmpeg test exists for this check"


class Recorder:
    """Collects the evidence of ONE job. Create it lazily at the first failure."""

    def __init__(self, job_id: int, name: str):
        self.dir = EVIDENCE / str(job_id)
        self.job_id, self.name = job_id, name
        self.dir.mkdir(parents=True, exist_ok=True)
        self.events: list[dict] = []
        self.failed_ids: list[str] = []
        self.has_original = (self.dir / "original_failed.mp4").exists()

    def _event(self, **kw) -> None:
        self.events.append({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **kw})
        (self.dir / "repair_log.json").write_text(json.dumps({"job_id": self.job_id, "name": self.name, "events": self.events}, ensure_ascii=False, indent=1), encoding="utf-8")

    def capture_failed(self, mp4: Path | None, qc_result: dict | None, failed: list[dict], attempt: int) -> None:
        """Copy the failed video BEFORE any repair touches it (never overwrites earlier evidence)."""
        ids = [c["id"] for c in failed]
        copied = ""
        if mp4 and mp4.exists():
            target = self.dir / ("original_failed.mp4" if not self.has_original else f"after_repair{attempt}_failed.mp4")
            if not target.exists():
                shutil.copy2(mp4, target)
            copied = target.name
            if target.name == "original_failed.mp4":
                self.has_original = True
                self.failed_ids = ids
                (self.dir / "original_hash.txt").write_text(f"{sha256(target)}  {target.name}  {target.stat().st_size} bytes  {time.strftime('%Y-%m-%dT%H:%M:%S')}\n", encoding="utf-8")
                (self.dir / "original_qc.json").write_text(json.dumps(qc_result or {"failed": failed, "note": "no full QC report (stage error)"}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        self._event(kind="failure_detected", attempt=attempt, failed_checks=ids, details=[c.get("detail", "")[:160] for c in failed], evidence_file=copied)

    def log_repair(self, plan: dict) -> None:
        self._event(kind="repair_started", attempt=plan["attempt"], action=plan["action"], params=plan["params"], swap_story=plan["swap_story"])

    def log(self, kind: str, **kw) -> None:
        self._event(kind=kind, **kw)

    def finalize(self, mp4: Path | None, qc_result: dict | None, note: str = "") -> dict:
        """Copy the final video, measure BOTH files independently, write the comparison, return the verdict."""
        verdict = {"verified": False, "status": "unverified", "reason": note}
        orig = self.dir / "original_failed.mp4"
        rep = self.dir / "repaired.mp4"
        if mp4 and mp4.exists():
            shutil.copy2(mp4, rep)
            (self.dir / "repaired_hash.txt").write_text(f"{sha256(rep)}  repaired.mp4  {rep.stat().st_size} bytes  {time.strftime('%Y-%m-%dT%H:%M:%S')}\n", encoding="utf-8")
        (self.dir / "repaired_qc.json").write_text(json.dumps(qc_result or {}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        if orig.exists() and rep.exists():
            mo, mr = measure(orig), measure(rep)
            rows, ok_all, verifiable = [], True, 0
            for cid in self.failed_ids:
                so, do = retest(cid, mo)
                sr, dr = retest(cid, mr)
                rows.append((cid, so, do, sr, dr))
                if so != "unverified":
                    verifiable += 1
                    if so != "fail":
                        ok_all = False  # the independent test does not confirm that the original was defective
                    if sr != "pass":
                        ok_all = False
                else:
                    ok_all = False
            different = mo["sha256"] != mr["sha256"]
            if not different:
                verdict = {"verified": False, "status": "NOT REPAIRED", "reason": "the repaired file is byte-identical to the failed file"}
            elif verifiable and ok_all and (qc_result or {}).get("passed"):
                verdict = {"verified": True, "status": "REPAIR VERIFIED", "reason": "every originally failed check fails on the original and passes on the repaired file (independent ffprobe/ffmpeg)"}
            elif verifiable == 0:
                verdict = {"verified": False, "status": "UNVERIFIED", "reason": "no independent test exists for the failed checks; not claiming success"}
            else:
                verdict = {"verified": False, "status": "REPAIR FAILED", "reason": "an originally failed check still fails on the repaired file, or the original defect was not confirmed independently"}
            self._report(mo, mr, rows, verdict)
        else:
            self._report(None, None, [], {**verdict, "reason": verdict["reason"] or "original or repaired video missing; evidence is logs only"})
        self._event(kind="final_verdict", **verdict)
        return verdict

    def _report(self, mo, mr, rows, verdict) -> None:
        lines = [f"# Repair evidence: job {self.job_id} ({self.name})", "", f"**VERDICT: {verdict['status']}**  {verdict['reason']}", ""]
        if mo and mr:
            keys = ["sha256", "bytes", "duration_s", "width", "height", "fps", "has_audio", "frame0_brightness", "frame_0_5s_brightness", "black_segments", "freeze_segments", "mean_volume_db", "max_volume_db", "loudness_lufs"]
            lines += ["## Independent measurements (ffprobe + ffmpeg)", "", "| metric | original_failed.mp4 | repaired.mp4 |", "|---|---|---|"]
            lines += [f"| {k} | {str(mo[k])[:24] if k == 'sha256' else mo[k]} | {str(mr[k])[:24] if k == 'sha256' else mr[k]} |" for k in keys]
            lines += ["", "## The checks that originally failed", "", "| check | original (independent) | repaired (independent) |", "|---|---|---|"]
            lines += [f"| {c} | {so}: {do} | {sr}: {dr} |" for c, so, do, sr, dr in rows]
        lines += ["", "## Timeline", ""] + [f"- {e['ts']} {e['kind']} {({k: v for k, v in e.items() if k not in ('ts', 'kind')})}" for e in self.events]
        (self.dir / "comparison_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
