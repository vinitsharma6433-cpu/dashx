"""The 14 agents and the Production Manager (central orchestrator).

Each agent has ONE responsibility and re-uses the existing, proven DASHX code (bridge.py) instead of replacing it.
Where plain Python can do the job reliably, no AI model is used; Gemma (Ollama) is only used by the Story Writer,
with the hand-written bank as the reliable fallback.

  1 Research         season/topic hints and what the history says is under-used
  2 Story Writer     picks or writes a story (bank first-class, Gemma optional)
  3 Script Doctor    Story Quality Score 0-100, rejects weak stories
  4 Character Dir.   checks roles, personalities, balances who appears
  5 Scene Director   picks background (day/sunset), keeps >=3 different visuals and an end card
  6 Voice            Kokoro Hindi voice per scene (make_voice.py)
  7 Animation        timing fit + subtitle widths + revideo render (fit_reel.py, dist/reel.js)
  8 Video Editor     final files: ready folder, manifest, LIST.md
  9 Quality Insp.    qc.inspect(): 17 checks, score 0-100
 10 Auto Repair      repair.plan(): reruns only the responsible stage, max 3 attempts
 11 Thumbnail        9:16 cover with Hindi title
 12 SEO              title, Hindi description, hashtags, tags, keywords, SEO score
 13 Publishing       optional YouTube upload (AUTO_UPLOAD=false by default)
 14 Production Mgr   this module's ProductionManager
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import traceback
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import ROOT, backup, db, evidence, log, ops, qc, repair, seo, spell, thumbnail, youtube
from . import story as story_mod
from .bridge import PY, daily, fit_reel, make_stories as ms
from .config import Config, load


class StageError(Exception):
    pass


@dataclass
class Job:
    id: int
    name: str
    day: str
    story: dict
    script: dict
    story_q: dict = field(default_factory=dict)
    params: dict = field(default_factory=lambda: {"voice_speed": 1.0, "fit_safety": 0.35, "thumb_variant": 0})
    thumb: Path | None = None
    seo: dict | None = None
    qc: dict | None = None
    repairs: int = 0
    t0: float = field(default_factory=time.time)


def ready_dir(day: str) -> Path:
    return ROOT / "output" / "ready" / day


def run_cmd(cmd: list[str], timeout: int) -> tuple[int, str]:
    return daily.run(cmd, timeout)


# ------------------------------------------------------------------------------------------------------
class ResearchAgent:
    SEASON = {6: "बारिश", 7: "बारिश", 8: "बारिश", 9: "बारिश", 10: "पतंग", 1: "पतंग"}

    def brief(self, day: str) -> dict:
        usage = db.character_usage()
        under = sorted(story_mod.PROFILES, key=lambda c: usage.get(c, 0))[:4]
        return {"season_word": self.SEASON.get(int(day[5:7]), ""), "underused": under, "usage": usage, "weak_stages": db.template_failure_rates()}


class StoryWriterAgent:
    def __init__(self, mgr: "ProductionManager"):
        self.m, self.llm, self.ideas, self.gemma_used = mgr, None, None, 0

    def _gemma(self, brief):
        m = self.m
        if self.llm is None:
            from purffle_shorts.config import Settings
            from purffle_shorts.llm import LLM
            self.llm = LLM(Settings(llm_provider="ollama", llm_model=daily.GEMMA))
            self.ideas = ms.plan(self.llm, m.history, m.cfg.DAILY_REEL_LIMIT + 4)
        return daily.story_from_gemma(self.llm, self.ideas, m.history, m.batch_titles, m.closings, m.mins)

    def write(self, brief: dict, exclude: list[str]) -> tuple[dict, dict] | None:
        m, cfg = self.m, self.m.cfg
        if cfg.ALLOW_NARRATION and cfg.SOURCE in ("auto", "gemma") and m.gemma_ready and self.gemma_used < cfg.GEMMA_SLOTS_PER_RUN:
            self.gemma_used += 1
            try:
                st = self._gemma(brief)
                if st:
                    q = story_mod.score_story(st, ref=m.ref)
                    if q["score"] >= cfg.MIN_STORY_SCORE:
                        return st, q
                    log.warn(f"Gemma story rejected, story score {q['score']}: {q['notes']}")
            except Exception as e:
                log.warn(f"Gemma story failed: {e}")
        if cfg.SOURCE == "gemma":
            return None
        return self._bank(brief, exclude)

    def _bank(self, brief: dict, exclude: list[str]) -> tuple[dict, dict] | None:
        m, cfg = self.m, self.m.cfg
        done = " ".join(m.history.recent_titles(500) + m.batch_titles + exclude)
        seen = daily.recent_cast(m.history, m.batch_casts)
        cands = []
        sources = [(b, daily.from_dialogue_data, "stories/dialogue_bank.md") for b in daily.parse_dialogue_bank()]
        if cfg.ALLOW_NARRATION:
            sources += [(b, daily.from_llm_data, "stories/bank.md") for b in daily.parse_bank()]
        for i, (b, builder, where) in enumerate(sources):
            if b["title_hi"] in done or b["title_en"] in done:
                continue
            data = {"title_hi": b["title_hi"], "title_en": b["title_en"], "plot_en": b["plot_en"], "scenes": b["rows"], "closing_hi": b["closing"], "hook": b.get("hook", ""), "card": b.get("card", ""), "series": b.get("series", ""), "ep": b.get("ep", "")}
            st, probs = builder(data, i, m.mins)
            if st:
                probs += daily.story_problems(st, m.history, m.batch_titles, m.closings)
            if not st or probs:
                log.warn(f"bank story '{b['title_en']}' skipped: {'; '.join(probs[:2])}")
                continue
            st["writer"], st["idea"] = f"hand-written story bank ({where})", b["title_en"]
            q = story_mod.score_story(st, ref=m.ref)
            if q["score"] < cfg.MIN_STORY_SCORE:
                log.warn(f"bank story '{b['title_en']}' rejected: score {q['score']} {q['notes']}")
                continue
            cast = story_mod.cast_of(st)
            text = " ".join(s["line"] for s in st["scenes"])
            rank = q["score"] + 6 * len(cast - seen) + 2 * sum(1 for c in cast if brief["usage"].get(c, 0) == 0) + (4 if brief["season_word"] and brief["season_word"] in text else 0)
            cands.append((rank, i, st, q))
        if not cands:
            return None
        cands.sort(key=lambda t: (-t[0], t[1]))
        return cands[0][2], cands[0][3]


class ScriptDoctorAgent:
    """Story Quality Score. (The Gemma path already ran purffle's Script Doctor two-pass.)"""

    def review(self, story: dict, ref: dict, cfg: Config) -> dict:
        q = story_mod.score_story(story, ref=ref)
        q["approved"] = q["score"] >= cfg.MIN_STORY_SCORE
        return q


class CharacterDirectorAgent:
    def assign(self, story: dict) -> list[str]:
        cast = sorted(story_mod.cast_of(story))
        story["personalities"] = {c: story_mod.PROFILES[c]["trait"] for c in cast}
        return cast


class SceneDirectorAgent:
    EVENING = ("शाम", "सूरज ढल", "आख़िरी गेंद")

    def plan(self, story: dict) -> list[str]:
        notes = []
        text = " ".join(s["line"] for s in story["scenes"])
        if any(w in text for w in self.EVENING):
            for s in story["scenes"]:
                s["params"]["sunset"] = True
            notes.append("background: sunset (the story is set in the evening)")
        assert len({s["template"] for s in story["scenes"]}) >= 3, "need at least 3 different visuals"
        return notes or ["background: day"]


class VoiceAgent:
    def run(self, job: Job) -> None:
        code, out = run_cmd([str(PY), "scripts/make_voice.py", job.name, "hm_omega", str(job.params["voice_speed"])], 900)
        if code != 0:
            raise StageError(f"voice failed: {out[-200:]}")


class AnimationAgent:
    def fit(self, job: Job) -> list[str]:
        ok, notes = fit_reel.fit(job.name, job.params["fit_safety"])
        if not ok:
            raise StageError("; ".join(notes))
        return notes

    def render(self, job: Job) -> None:
        started = time.time()
        code, out = run_cmd(["node", "dist/reel.js", job.name], 1800)
        mp4 = ROOT / "output" / "reels" / f"{job.name}.mp4"
        if code != 0 or not mp4.exists() or mp4.stat().st_mtime < started:
            raise StageError(f"render failed: {out[-250:]}")
        fault = job.params.get("_fault")
        if fault and not job.params.get("_fault_always"):
            job.params.pop("_fault")
        if fault == "black_first_frame":
            # CHAOS TEST HOOK (only when FACTORY_INJECT_FAULT is set): reproduce the old bug, a fade from black,
            # to prove that QC catches it and the repair loop fixes it. Never active in normal runs.
            tmp = mp4.with_suffix(".fault.mp4")
            subprocess.run([qc.FFMPEG, "-v", "error", "-y", "-i", str(mp4), "-vf", "fade=t=in:st=0:d=0.8", "-c:a", "copy", str(tmp)], check=True)
            tmp.replace(mp4)
            log.warn("chaos test: injected a black first frame", job=job.name)


class QualityInspectorAgent:
    def inspect(self, job: Job) -> dict:
        return qc.inspect(job.name, job.thumb)


class ThumbnailAgent:
    def run(self, job: Job) -> Path:
        out = ROOT / "factory" / "data" / "tmp" / job.name / "thumb.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)
        return thumbnail.make(job.name, job.script["title"], ROOT / "output" / "reels" / f"{job.name}.mp4", out, job.params["thumb_variant"])


class SEOAgent:
    def run(self, job: Job, cast: list[str]) -> dict:
        return seo.generate(job.script, job.story_q.get("categories", ["Gali Cricket"]), cast)


class PublishingAgent:
    def run(self, job: Job, cfg: Config, video: Path, thumb: Path | None, index: int) -> dict:
        return youtube.publish_job(job.id, video, thumb, job.seo, cfg, index)


class VideoEditorAgent:
    """Final files: copies the reel, thumbnail and SEO files to output/ready/<date>/ and keeps LIST.md current."""

    def finalize(self, job: Job, cast: list[str]) -> Path:
        rd = ready_dir(job.day)
        rd.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "output" / "reels" / f"{job.name}.mp4", rd / f"{job.name}.mp4")
        thumb_name = ""
        if job.thumb and job.thumb.exists():
            thumb_name = f"{job.name}-thumb.jpg"
            shutil.copy2(job.thumb, rd / thumb_name)
        if job.seo:
            (rd / f"{job.name}.seo.json").write_text(json.dumps(job.seo, ensure_ascii=False, indent=1), encoding="utf-8")
            (rd / f"{job.name}.seo.md").write_text(self._seo_md(job), encoding="utf-8")
        mf = rd / "manifest.json"
        manifest = json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else []
        manifest = [m for m in manifest if m.get("file") != f"{job.name}.mp4"]
        manifest.append({"file": f"{job.name}.mp4", "cover": thumb_name, "title": job.script["title"], "plot": job.story["plot_en"],
                         "characters": ", ".join(c.capitalize() for c in cast), "duration": round(job.qc["_dur"], 1) if job.qc and "_dur" in job.qc else None,
                         "qc": job.qc["score"] if job.qc else None, "seo": job.seo["seo_score"] if job.seo else None, "story": job.story_q.get("score")})
        mf.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        rows = [f"# Ready reels {job.day}", "", "| file | thumbnail | title | plot | characters | sec | QC | SEO | story |", "|---|---|---|---|---|---|---|---|---|"]
        for m in manifest:
            rows.append(f"| {m['file']} | {m.get('cover') or m.get('cover', '')} | {m['title']} | {m['plot']} | {m['characters']} | {m.get('duration')} | {m.get('qc', '')} | {m.get('seo', '')} | {m.get('story', '')} |")
        (rd / "LIST.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
        return rd / f"{job.name}.mp4"

    @staticmethod
    def _seo_md(job: Job) -> str:
        s = job.seo
        return (f"# {s['title']}\n\nSEO score: {s['seo_score']}/100 {s['seo_notes'] or ''}\n\n## Description\n{s['description']}\n\n"
                f"## Hashtags\n{' '.join(s['hashtags'])}\n\n## Tags\n{', '.join(s['tags'])}\n\n## Keyword suggestions\n{', '.join(s['keyword_suggestions'])}\n\n"
                f"AI-generated content: declared (cartoon with an AI voice).\n")


# ------------------------------------------------------------------------------------------------------
class ProductionManager:
    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or load()
        self.research, self.writer = ResearchAgent(), StoryWriterAgent(self)
        self.doctor, self.chars, self.scenes = ScriptDoctorAgent(), CharacterDirectorAgent(), SceneDirectorAgent()
        self.voice, self.anim, self.qa = VoiceAgent(), AnimationAgent(), QualityInspectorAgent()
        self.thumbs, self.seo, self.publisher, self.editor = ThumbnailAgent(), SEOAgent(), PublishingAgent(), VideoEditorAgent()
        self.history = daily.History(ms.USED)
        self.mins = ms.template_minimums()
        self.batch_titles: list[str] = []
        self.batch_casts: list[set] = []
        self.closings: list[str] = []
        self.ref: dict = {}
        self.gemma_ready = False

    # ---- helpers ----
    def _timed(self, job: Job, stage: str, fn):
        t = time.time()
        log.info(f"stage {stage}", job=job.name, stage=stage)
        try:
            out = fn()
        except Exception as e:
            db.log_stage(job.id, stage, "failed", time.time() - t, str(e))
            raise
        db.log_stage(job.id, stage, "ok", time.time() - t, "" if not isinstance(out, list) else "; ".join(out)[:300])
        return out

    def _build(self, job: Job, start: str) -> list[dict]:
        """Run voice -> fit -> render -> thumbnail from `start`. A stage error becomes a failed check (with its stage)."""
        order = ["voice", "fit", "render", "thumbnail"]
        for st in order[order.index(start):]:
            try:
                if st == "voice":
                    self._timed(job, st, lambda: self.voice.run(job))
                elif st == "fit":
                    self._timed(job, st, lambda: self.anim.fit(job))
                elif st == "render":
                    self._timed(job, st, lambda: self.anim.render(job))
                elif st == "thumbnail" and self.cfg.AUTO_THUMBNAIL:
                    job.thumb = self._timed(job, st, lambda: self.thumbs.run(job))
            except (StageError, RuntimeError) as e:
                return [{"id": f"{st}_error", "stage": st, "detail": str(e)[:300], "weight": 10, "ok": False, "hard": True}]
        return []

    def _new_story(self, brief, exclude, run_id, day) -> Job | None:
        got = self.writer.write(brief, exclude)
        if not got:
            return None
        story, q = got
        q = {**q, **self.doctor.review(story, self.ref, self.cfg)}
        cast = self.chars.assign(story)
        notes = self.scenes.plan(story)
        name, script = daily.write_script(story, self.mins)
        self.history.add_used(day, name, f"{story['title_hi']} ({story['title_en']})", story["plot_en"], story["closing"])
        self.batch_titles.append(f"{story['title_hi']} ({story['title_en']})")
        self.batch_casts.append(set(cast))
        self.closings.append(story["closing"])
        self.ref = story_mod.corpus()
        job_id = db.create_job(run_id, name, day, story["writer"][:40])
        db.update_job(job_id, title=story["title_hi"], plot=story["plot_en"], cast_json=json.dumps(cast), category=",".join(q["categories"]), story_score=q["score"])
        db.save_story({"name": name, "title": story["title_hi"], "plot": story["plot_en"], "closing": story["closing"], "category": ",".join(q["categories"]),
                       "cast": cast, "templates": [s["template"] for s in story["scenes"]], "score": q["score"], "approved": True, "source": story["writer"][:40]})
        log.info(f"story approved: {name} score {q['score']} cast {cast}; {notes[0]}", job=name)
        return Job(job_id, name, day, story, script, q)

    # ---- one reel, start to finish, with automatic repair ----
    def produce(self, run_id: int, day: str, index: int, brief: dict) -> dict:
        job = self._new_story(brief, [], run_id, day)
        if job is None:
            return {"name": "-", "status": "failed", "error": "no approved story available"}
        kind, _, rest = os.environ.get("FACTORY_INJECT_FAULT", "").partition("@")
        nth, _, mode = rest.partition(":")  # e.g. black_first_frame@1 (once) or black_first_frame@1:always (persistent)
        if kind and nth.isdigit() and int(nth) == index + 1:
            job.params["_fault"] = kind
            job.params["_fault_always"] = mode == "always"
        return self._finish(job, "voice", index, brief, run_id)

    def _finish(self, job: Job, start: str, index: int, brief: dict, run_id: int) -> dict:
        cfg = self.cfg
        cast = sorted(story_mod.cast_of(job.story)) if job.story.get("scenes") else json.loads(db.q("SELECT cast_json FROM jobs WHERE id=?", (job.id,))[0]["cast_json"] or "[]")
        attempt = 0
        rec: evidence.Recorder | None = None
        orig_job = job
        failed = self._build(job, start)
        while True:
            if not failed:
                if not cfg.AUTO_QC:
                    db.update_job(job.id, status="unchecked", error="AUTO_QC=false: not checked, not marked ready", finished=db.now(), seconds=time.time() - job.t0)
                    log.warn("AUTO_QC=false: reel is NOT marked ready", job=job.name)
                    return {"name": job.name, "status": "unchecked"}
                res = self._timed(job, "qc", lambda: self.qa.inspect(job))
                job.qc = res
                for c in res["failed"]:
                    db.add_failure(job.id, c["id"], c["stage"], c["detail"])
                if res["score"] >= cfg.MIN_QC_SCORE and res["passed"]:
                    break
                failed = res["failed"] or [{"id": "score_below_target", "stage": "render", "detail": f"score {res['score']} < {cfg.MIN_QC_SCORE}"}]
            if not cfg.AUTO_REPAIR or attempt >= cfg.MAX_REPAIRS:
                verdict = None
                if rec is not None:
                    verdict = rec.finalize(ROOT / "output" / "reels" / f"{job.name}.mp4", job.qc, "repair attempts exhausted")
                    db.add_repair(orig_job.id, attempt, "evidence", f"{verdict['status']}: {verdict['reason'][:120]}")
                db.update_job(job.id, status="failed", qc_score=(job.qc or {}).get("score"), repairs=attempt, finished=db.now(), seconds=time.time() - job.t0,
                              error="; ".join(f"{c['id']}: {c['detail'][:60]}" for c in failed[:3]))
                log.error(f"FAILED after {attempt} repair attempt(s): {[c['id'] for c in failed]}", job=job.name)
                return {"name": job.name, "status": "failed", "qc": (job.qc or {}).get("score"), "repairs": attempt, "error": failed[0]["detail"][:120]}
            # EVIDENCE: keep the failed video before any repair can overwrite it
            if rec is None:
                rec = evidence.Recorder(orig_job.id, orig_job.name)
            rec.capture_failed(ROOT / "output" / "reels" / f"{job.name}.mp4", job.qc if job.qc and not job.qc.get("passed") else None, failed, attempt)
            attempt += 1
            plan = repair.plan(failed, attempt)
            rec.log_repair(plan)
            job.params.update(plan["params"])
            log.warn(plan["action"], job=job.name)
            db.add_repair(job.id, attempt, plan["action"], "started")
            job.repairs = attempt
            if plan["swap_story"]:
                nxt = self._new_story(brief, [job.story["title_en"], job.story["title_hi"]], run_id, job.day)
                if nxt is None:
                    db.add_repair(job.id, attempt, plan["action"], "no other story available")
                    failed = failed
                    continue
                db.update_job(job.id, status="replaced", error=f"replaced by {nxt.name}", finished=db.now())
                nxt.repairs = attempt
                if job.params.get("_fault_always"):
                    nxt.params.update({"_fault": job.params["_fault"], "_fault_always": True})
                rec.log("story_swapped", new_job=nxt.name)
                job, start = nxt, "voice"
            else:
                start = plan["start"] if plan["start"] != "story" else "voice"
            failed = self._build(job, start)
            db.add_repair(job.id, attempt, plan["action"], "rebuilt" if not failed else f"still failing: {failed[0]['id']}")

        # ---- passed ----
        if rec is not None:
            verdict = rec.finalize(ROOT / "output" / "reels" / f"{job.name}.mp4", job.qc)
            db.add_repair(orig_job.id, attempt, "evidence", f"{verdict['status']}: {verdict['reason'][:120]}")
            log.info(f"repair evidence: {verdict['status']} ({rec.dir})", job=job.name)
            if not verdict["verified"]:
                db.update_job(job.id, status="failed", repairs=attempt, finished=db.now(), error=f"QC passed but independent verification says {verdict['status']}")
                return {"name": job.name, "status": "failed", "qc": job.qc["score"], "repairs": attempt, "error": f"repair not independently verified: {verdict['status']}"}
        job.qc["_dur"] = next((float(c["detail"].split("s")[0]) for c in job.qc["checks"] if c["id"] == "duration"), None)
        if self.cfg.AUTO_SEO:
            job.seo = self._timed(job, "seo", lambda: self.seo.run(job, cast))
        db.update_job(job.id, qc_score=job.qc["score"], seo_score=(job.seo or {}).get("seo_score"), duration_s=job.qc["_dur"], repairs=job.repairs)
        final = self._timed(job, "finalize", lambda: self.editor.finalize(job, cast))
        pub = {"status": "n/a"}
        if self.cfg.AUTO_UPLOAD and job.seo:
            pub = self._timed(job, "publish", lambda: self.publisher.run(job, self.cfg, final, job.thumb, index))
        db.update_job(job.id, status="ready", finished=db.now(), seconds=time.time() - job.t0)
        log.info(f"READY qc={job.qc['score']} seo={(job.seo or {}).get('seo_score')} repairs={job.repairs}", job=job.name)
        return {"name": job.name, "status": "ready", "qc": job.qc["score"], "seo": (job.seo or {}).get("seo_score"), "story": job.story_q.get("score"),
                "repairs": job.repairs, "seconds": round(time.time() - job.t0), "publish": pub["status"], "title": job.script["title"]}

    # ---- resume interrupted jobs ----
    def resume(self, run_id: int, day: str, brief: dict) -> list[dict]:
        out = []
        for row in db.q("SELECT * FROM jobs WHERE status='running'"):
            sp = ROOT / "reels" / row["name"] / "script.json"
            if not sp.exists():
                db.update_job(row["id"], status="failed", error="interrupted before a script existed", finished=db.now())
                continue
            script = json.loads(sp.read_text(encoding="utf-8"))
            story = {"title_hi": script["title"], "title_en": row["name"], "plot_en": script["story"]["plot"], "closing": script["story"].get("closing", ""), "scenes": []}
            job = Job(row["id"], row["name"], row["day"] or day, story, script, {"score": row["story_score"], "categories": (row["category"] or "Gali Cricket").split(",")})
            has_audio = (ROOT / "reels" / row["name"] / "audio" / "durations.json").exists()
            log.warn(f"resuming interrupted job {row['name']} from {'fit' if has_audio else 'voice'}", job=row["name"])
            out.append(self._finish(job, "fit" if has_audio else "voice", 0, brief, run_id))
        return out

    # ---- a whole day ----
    def run_day(self, count: int | None = None, force: bool = False) -> dict:
        cfg = self.cfg
        day = date.today().isoformat()
        count = count or cfg.DAILY_REEL_LIMIT
        if not ops.acquire_lock():
            log.error("another production run is active (lock held); not starting a second one")
            return {"status": "locked"}
        ops.set_stop(False)
        health = db.ensure_healthy()
        if health["status"] != "ok":
            log.error(f"database was damaged: {health}")
        else:
            db.snapshot()
        run_id = db.start_run(day, count, cfg.SOURCE)
        results: list[dict] = []
        try:
            d = ops.disk()
            if d["free_gb"] < cfg.MIN_FREE_GB:
                db.finish_run(run_id, "aborted", f"only {d['free_gb']} GB free")
                log.error(f"stopping: only {d['free_gb']} GB free disk")
                return {"status": "aborted", "reason": "disk"}
            if not any(p.name.startswith("daily-") and time.strftime("%Y%m%d") in p.name for p in backup.listing()):
                log.info(f"backup: {backup.create('daily').name}")
            if cfg.SOURCE != "bank":
                self.gemma_ready = daily.gemma_status()[0] == "READY"
            code, out = run_cmd(["node", "node_modules/typescript/bin/tsc"], 300)
            if code != 0:
                raise RuntimeError(f"tsc failed: {out[-300:]}")
            self.ref = story_mod.corpus()
            self.closings = daily.known_closings(self.history)
            brief = self.research.brief(day)
            results += self.resume(run_id, day, brief)
            target = count if force else max(0, count - db.passed_today(day))
            if target == 0 and not results:
                log.info(f"already {db.passed_today(day)} ready reels today (use --force for more)")
            i = 0
            while db.q("SELECT COUNT(*) n FROM jobs WHERE run_id=? AND status='ready'", (run_id,))[0]["n"] < target and i < target + 4:
                if ops.stop_requested():
                    log.warn("STOP requested: finishing here")
                    break
                i += 1
                try:
                    results.append(self.produce(run_id, day, i - 1, brief))
                except Exception as e:  # one job failing must never stop the day
                    log.error(f"job crashed: {e}", stage="crash")
                    log.event("ERROR", "traceback", tb=traceback.format_exc()[-600:])
                    results.append({"name": "-", "status": "failed", "error": f"{type(e).__name__}: {e}"})
                failed = sum(1 for r in results if r["status"] != "ready")
                if failed >= cfg.MAX_FAILED_STORIES:  # a systematic problem (a rule, a template): stop instead of burning minutes on more stories
                    log.error(f"stopping: {failed} stories failed in this run (limit {cfg.MAX_FAILED_STORIES})")
                    break
            ok = sum(1 for r in results if r["status"] == "ready")
            db.finish_run(run_id, "done" if ok >= target else "partial", f"{ok} ready of {target}")
            self.report(run_id, day, results, brief)
            ops.cleanup()
            return {"status": "done" if ok >= target else "partial", "ready": ok, "target": target, "results": results, "run_id": run_id}
        finally:
            ops.release_lock()

    def retry(self, job_id: int) -> dict:
        rows = db.q("SELECT * FROM jobs WHERE id=?", (job_id,))
        if not rows:
            return {"status": "not found"}
        row = rows[0]
        if not ops.acquire_lock():
            return {"status": "locked"}
        try:
            code, out = run_cmd(["node", "node_modules/typescript/bin/tsc"], 300)
            script = json.loads((ROOT / "reels" / row["name"] / "script.json").read_text(encoding="utf-8"))
            story = {"title_hi": script["title"], "title_en": row["name"], "plot_en": script["story"]["plot"], "closing": script["story"].get("closing", ""), "scenes": []}
            job = Job(job_id, row["name"], row["day"], story, script, {"score": row["story_score"], "categories": ["Gali Cricket"]})
            db.update_job(job_id, status="running", error=None, started=db.now())
            self.ref = story_mod.corpus()
            return self._finish(job, "voice", 0, self.research.brief(row["day"]), row["run_id"])
        finally:
            ops.release_lock()

    # ---- daily report ----
    def report(self, run_id: int, day: str, results: list[dict], brief: dict) -> Path:
        rd = ready_dir(day)
        rd.mkdir(parents=True, exist_ok=True)
        bank_left = sum(1 for b in daily.parse_bank() if b["title_hi"] not in " ".join(self.history.recent_titles(500)))
        d = ops.disk()
        lines = [f"# Daily report {day} (run {run_id})", "",
                 f"- ready: {sum(r['status'] == 'ready' for r in results)} / failed: {sum(r['status'] == 'failed' for r in results)} / unchecked: {sum(r['status'] == 'unchecked' for r in results)}",
                 f"- Gemma: {daily.gemma_status()[0]} (used {self.writer.gemma_used} slot(s)); bank stories left: {bank_left}",
                 f"- disk free {d['free_gb']} GB; ready folder {d['ready_mb']} MB; backups {d['backups_mb']} MB",
                 f"- upload: AUTO_UPLOAD={self.cfg.AUTO_UPLOAD}", "",
                 "| name | status | QC | SEO | story | repairs | sec | note |", "|---|---|---|---|---|---|---|---|"]
        for r in results:
            lines.append(f"| {r['name']} | {r['status']} | {r.get('qc', '')} | {r.get('seo', '')} | {r.get('story', '')} | {r.get('repairs', 0)} | {r.get('seconds', '')} | {r.get('error', '')} |")
        fails = db.q("SELECT j.name, f.check_id, f.stage, f.detail FROM failures f JOIN jobs j ON j.id=f.job_id WHERE j.run_id=? ORDER BY f.id", (run_id,))
        if fails:
            lines += ["", "## Failures seen (and repaired or not)"] + [f"- {f['name']}: {f['check_id']} [{f['stage']}] {f['detail'][:100]}" for f in fails]
        p = rd / "REPORT.md"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p
