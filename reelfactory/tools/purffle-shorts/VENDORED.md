# purffle-shorts, vendored for the DASHX story writer

- Source: https://github.com/Chamanrajragu/purffle-shorts (MIT, see `LICENSE`), commit
  `baaba035be13fa4aa2ebc31951d58ea141e2d74c` (2026-10-20), cloned with `git clone --depth 1`.
- Used for: only the script-writing part, the **idea planner** (`planner.py`) and the **Script Doctor**
  two-pass (`script.py`: grade, rewrite, grade again) on top of its LLM layer (`llm.py`).
- Called by `scripts/make_stories.py` (`npm run stories -- 5`).

## Kept (with changes)
| file | change |
|---|---|
| `purffle_shorts/llm.py` | only local providers left (Ollama, LM Studio); every key-based cloud provider and the Anthropic client removed |
| `purffle_shorts/script.py` | unchanged (writer helpers and Script Doctor) |
| `purffle_shorts/planner.py` | the "true and checkable" rule can be replaced through `settings.planner_rules`; the YouTube-search lookup was removed |
| `purffle_shorts/utils.py` | `requests` replaced by a small `urllib` client (no install needed); `download()` removed |
| `purffle_shorts/config.py` | rewritten: only language, length, local-LLM and Script Doctor settings. No upload, publish, API-key or webhook setting exists any more |
| `purffle_shorts/history.py` | rewritten: reads and writes `stories/used.md` instead of purffle's SQLite database (which also tracked uploads and views) |

## Removed
Upload and publishing: `youtube.py` (YouTube upload and scheduling), `crosspost.py` (TikTok, Instagram and other
networks), `notify.py` (webhooks), `studio.py` and `web/` (web app with publish buttons), `mcp_server.py`, `cli.py`,
`pipeline.py` (the autopilot loop that uploaded), `analytics.py`, `YT.py`.
Not needed (we render with revideo and kokoro): `render.py`, `overlays.py`, `ffmpeg.py`, `media.py`, `tts.py`,
`timing.py`, `sfx.py`, `clipper.py`, `seo.py`, `topics.py`, `doctor.py`.
Also removed: tests, docs, notebooks, examples, Docker files, other-language READMEs, packaging files, `.git`.

Nothing in this folder can post, upload or call a cloud service. `README.md` is the original, kept for reference
(it still describes the removed features).
