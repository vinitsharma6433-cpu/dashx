"""Auto Repair Agent (planning part). Given the failed QC checks it decides WHICH stage to rerun and with which
gentler settings. At most MAX_REPAIRS (default 3) attempts per reel; the pipeline records every attempt.

Stage order: story -> voice -> fit -> render -> thumbnail.   A repair reruns the earliest responsible stage and
everything after it, never anything before it.

  attempt 1: rerun the responsible stage as it was (fixes temporary tool errors)
  attempt 2: rerun with gentler settings (slower voice 0.95, more timing safety 0.6 s)
  attempt 3: give up on this story and rebuild the reel from a different story (when the cause is in the
             story or voice), otherwise one last rerun
"""

from __future__ import annotations

ORDER = ["story", "voice", "fit", "render", "thumbnail"]


def earliest(failed: list[dict]) -> str:
    stages = {c["stage"] for c in failed}
    return next(s for s in ORDER if s in stages)


def plan(failed: list[dict], attempt: int) -> dict:
    stage = earliest(failed)
    swap = stage == "story" or (attempt >= 3 and stage in ("voice", "fit"))
    params = {"voice_speed": 0.95 if attempt >= 2 else 1.0, "fit_safety": 0.6 if attempt >= 2 else 0.35, "thumb_variant": attempt}
    start = "story" if swap else stage
    why = "; ".join(f"{c['id']}: {c['detail'][:80]}" for c in failed[:3])
    return {"start": start, "swap_story": swap, "params": params, "attempt": attempt,
            "action": f"rerun from '{start}'" + (" with a new story" if swap else "") + f" (attempt {attempt}) because {why}"}
