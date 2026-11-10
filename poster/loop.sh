#!/usr/bin/env bash
# Self-dispatching poster loop: checks the queue every CHECK_EVERY seconds for up to LOOP_SECONDS, posts what is due.
# Every result is committed + pushed right after it exists (poster.py checkpoint), so a cancel or crash can never cause a duplicate.
# Exit 0 normally; writes .token_bad when poster.py reported an invalid Meta token (the workflow turns the run red once, at the end).
set -u
LOOP_SECONDS="${LOOP_SECONDS:-20700}"   # 5 h 45 min; GitHub stops a job at 6 h
CHECK_EVERY="${CHECK_EVERY:-300}"       # 5 min
git config user.name "dashx-poster"
git config user.email "dashx-poster@users.noreply.github.com"
git config merge.queuejson.name "DASHX queue.json merge"
git config merge.queuejson.driver "python poster/merge_queue.py %O %A %B"
export POSTER_CHECKPOINT=1
rm -f .token_bad
n=0
while [ "$SECONDS" -lt "$LOOP_SECONDS" ]; do
  n=$((n + 1))
  if [ -e STOP_POSTER ] || [ -e poster/STOP_POSTER ]; then echo "STOP_POSTER file found: loop ends, no next run"; touch .stopped; break; fi
  git pull --rebase -q --autostash origin main || { git rebase --abort 2>/dev/null; echo "::warning::pull failed this round"; }
  echo "--- check $n at $(TZ=Asia/Kolkata date '+%d %b %H:%M:%S') IST ($SECONDS s into the loop)"
  python poster/poster.py || touch .token_bad
  left=$((LOOP_SECONDS - SECONDS))
  [ "$left" -le 0 ] && break
  [ "$left" -lt "$CHECK_EVERY" ] && sleep "$left" || sleep "$CHECK_EVERY"
done
# last push attempt for anything not pushed yet
git add poster/queue.json
git diff --cached --quiet || git commit -q -m "Poster: update queue results"
for i in 1 2 3 4 5; do git pull --rebase -q --autostash origin main && git push -q origin HEAD:main && break; git rebase --abort 2>/dev/null; sleep $((i * 5)); done
echo "loop finished after $n checks"
