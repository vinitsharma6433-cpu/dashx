# DASHX Trust Ladder (owner-approved roadmap)

Owner: Vineet Sharma. This file is the plan the machine follows step by step.
The machine moves up a step ONLY when the written gate for that step is met.
The machine never edits this file or RULES.json. Only the owner does.

## Never loosened, at any step (permanent DENY)
- Tokens, secrets, env, accounts, OAuth scopes
- Posting schedule, slots, poster/**, queue.py, queue_config.json, youtube.py, qc.py, voices.json
- .github/**, RULES.json, RULES.sha256, guard.py, this file
- Engagement tricks, fake claims, copied text, false brand claims
- Any new Meta or Google permission (owner must approve in chat)

## Steps

### Step 1 - Watch (NOW)
ON: watchdog, self-heal, daily report at 21:00 IST, ALERT issue.
OFF: self-improvement, Scout apply.
Gate to Step 2: first autonomy run succeeded AND 2 reels posted cleanly after it (no new failure, no duplicate).

### Step 2 - Careful self-improvement
ON: self-improvement, max 1 change per day, 3 files, allowed files only, auto-revert watch.
Gate to Step 3: 7 days, zero reverts that hurt a post, zero missed slots.

### Step 3 - Wider self-improvement
Max 2 changes per day. Same allowed files, same blocked windows.
Gate to Step 4: 30 days, zero missed slots, zero Meta warnings, reel views not falling.

### Step 4 - Scout proposals with auto-apply (safe files only)
Scout may apply ONLY to: dialogue_bank.md, situations.json, characters.json, seo.py.
Every apply goes through guard.py and the 2-reel watch with auto-revert.
Gate: owner reads the monthly report and says yes in chat.

## How the machine reports
- Every day: status/daily.md says current step, gate progress (for example 3 of 7 days) and any blocker.
- Moving up a step is written to autonomy/log.md with the evidence.
- Any miss, warning or revert: drop one step down and raise a DASHX ALERT issue.

## Owner checks (2 minutes per week)
- Open status/daily.md. If the step is rising and no ALERT, do nothing.
- If ALERT or a Meta warning: set DASHX_AUTONOMY_ENABLED to false and ask Claude.
