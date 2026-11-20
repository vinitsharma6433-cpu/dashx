"""DASHX Autonomy, Phase 7: human-only alerts + the autonomy status. Standard library only. Free: one GitHub Issue, no other service.

ONLY for what the machine cannot fix by itself (it never fixes a token, an account or a key):
  Meta token expired / permission, YouTube token / secret, an account flagged or restricted, Gemini key invalid or the refill silent,
  Story Refill stopped by Gemini server / network errors on 2 consecutive refill days, the rule file changed, an auto-revert that could not finish.
It keeps exactly ONE open GitHub Issue titled "DASHX ALERT" with the exact steps in simple Hinglish (the Settings page and the secret NAME, never a
value). No duplicates: an open one is updated, extra open ones are closed, a new one is made only when none is open. When the problem is gone
the issue is closed by itself. A problem counts as gone when the NEWEST attempt of that network worked, so an old failure never keeps it open.

It also writes autonomy/status.json (green / yellow / red + today's trend) for the /status/ page. Secrets and error texts are never copied:
only the kind of problem and the reel title.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard  # noqa: E402
import ladder  # noqa: E402

ROOT = guard.ROOT
IST = guard.IST
TITLE = "DASHX ALERT"
LABEL = "dashx-alert"
LOW_STOCK = 12             # below this many stories left: a DASHX ALERT and a line in status/daily.md
CRITICAL_STOCK = 6         # below this: a LOUD alert (the posting and the schedule are never changed)
ALLOWED_OUT = {"autonomy/status.json", "status/daily.md"}      # the only files this module (and report.py) writes

META_RE = re.compile(r"token|oauth|expired|cannot call api|\b190\b|code 200|session has expired|permission|secrets missing", re.I)
YT_RE = re.compile(r"google token error|invalid_grant|invalid_client|unauthorized_client|secrets missing|invalid_request", re.I)
FLAG_RE = re.compile(r"flagged|restricted|suspend|disabled|checkpoint|action blocked|spam|violat|community guidelines|account (is )?(locked|limited)", re.I)
GEMINI_RE = re.compile(r"Gemini answered HTTP (400|401|403)")
# grading stopped (any reason) or the writer got a Gemini server / network error (HTTP 0 or 5xx). 400/401/403 stay GEMINI_KEY.
REFILL_ERR_RE = re.compile(r"grading stopped:|Gemini answered HTTP (0|5\d\d)\b")
REFILL_ERR_DAYS = 2        # alert only after this many CONSECUTIVE refill days with such an error (one bad day is usually a busy Gemini server)


@dataclass
class Problem:
    id: str
    title: str                      # one short Hinglish line
    what: str                       # what happened, Hinglish
    steps: list[str]
    evidence: str = ""              # reel title + network only (no error text)


@dataclass
class Signals:
    now: datetime
    posts: list[dict]
    refill_daily: str = ""
    usage: dict = field(default_factory=dict)
    log_text: str = ""
    learning: dict = field(default_factory=dict)
    trends: dict = field(default_factory=dict)
    watch: dict = field(default_factory=dict)
    rules_ok: bool = True
    rules_why: str = ""
    stops: list[str] = field(default_factory=list)
    ladder: dict = field(default_factory=dict)        # Trust Ladder state (autonomy/ladder.py), kept inside autonomy/status.json
    ladder_ok: bool = True                            # TRUST_LADDER.md still matches the hash sealed in RULES.json
    ladder_why: str = ""
    refill_errors: dict = field(default_factory=dict)  # error streak of the refill days, kept inside autonomy/status.json (see refill_streak)


def _rd(root: Path, rel: str, default):
    try:
        return json.loads((root / rel).read_text(encoding="utf-8"))
    except Exception:
        return default


def load_signals(root: Path = ROOT, now: datetime | None = None) -> Signals:
    now = (now or datetime.now(IST)).astimezone(IST)
    ok, why = True, ""
    try:
        guard.load_rules()
    except guard.RulesTampered as e:
        ok, why = False, str(e)

    def text(rel):
        try:
            return (root / rel).read_text(encoding="utf-8")
        except Exception:
            return ""
    stops = [n for n in ("STOP_AUTONOMY", "STOP_POSTER", "STOP_QUEUE", "STOP_REFILL") if (root / n).exists() or (root / "reelfactory" / n).exists()]
    lok, lwhy = ladder.ladder_file_ok(root) if ok else (True, "")
    return Signals(now, _rd(root, "poster/queue.json", {"posts": []}).get("posts", []), text("reelfactory/stories/refill_daily.txt"),
                   _rd(root, "reelfactory/stories/refill_usage.json", {}), text("autonomy/log.md"), _rd(root, "autonomy/learning.json", {}),
                   _rd(root, "autonomy/trends.json", {}), _rd(root, "autonomy/watch.json", {}), ok, why, stops,
                   ladder.load(root), lok, lwhy, _rd(root, "autonomy/status.json", {}).get("refill_errors", {}) or {})


def _refill_day(line: str):
    m = re.search(r"Story refill (\d{4}-\d\d-\d\d)", line or "")
    return datetime.fromisoformat(m.group(1)).date() if m else None


def refill_streak(prev: dict, refill_daily: str) -> dict:
    """How many CONSECUTIVE refill days ended with grading stopped or a Gemini HTTP 0/5xx. Pure.
    Keyed by the refill day, not by the run, so running alerts many times on one day never counts that day twice.
    `before` = the streak up to the previous refill day, so a re-run of the same day that comes out clean drops the streak to 0.
    A refill day the machine never saw (a gap of more than one day) starts the streak again at this day."""
    prev = prev if isinstance(prev, dict) else {}
    day = _refill_day(refill_daily)
    if not day:
        return dict(prev)
    err = bool(REFILL_ERR_RE.search(refill_daily))
    try:
        pday = datetime.fromisoformat(str(prev.get("day", ""))).date()
    except ValueError:
        pday = None
    if pday == day:
        before = int(prev.get("before", 0) or 0)
    elif pday and (day - pday).days == 1:
        before = int(prev.get("streak", 0) or 0)
    else:
        before = 0
    return {"day": day.isoformat(), "error": err, "before": before, "streak": before + 1 if err else 0}


# ---------------------------------------------------------------- what is wrong (pure)
def _latest(posts: list[dict], net: str, now: datetime, hours: int = 72):
    """The newest post (already due, within `hours`) that has a result for this network."""
    best = None
    for p in posts:
        try:
            due = datetime.fromisoformat(p["when"])
        except Exception:
            continue
        if due > now or now - due > timedelta(hours=hours) or net not in p.get("results", {}):
            continue
        if best is None or due > datetime.fromisoformat(best["when"]):
            best = p
    return best


def detect(s: Signals) -> list[Problem]:
    out: list[Problem] = []
    for net, nice, rx, pid in (("facebook", "Facebook", META_RE, "META_TOKEN"), ("instagram", "Instagram", META_RE, "META_TOKEN"), ("youtube", "YouTube", YT_RE, "YT_TOKEN")):
        p = _latest(s.posts, net, s.now)
        if not p:
            continue
        r = p["results"][net]
        err = str(r.get("error", ""))
        if r.get("ok") or r.get("skipped_late") or not err:
            continue
        if FLAG_RE.search(err):
            out.append(Problem("ACCOUNT_FLAGGED", f"{nice} account par rok ya warning aa sakti hai",
                               f"{nice} ne reel ko rok diya aur jawab mein 'flagged/restricted' jaisi baat aayi. Machine isko theek nahi kar sakti.",
                               [f"{nice} app ya website kholo → Account status / Support inbox / Notifications dekho.",
                                "Jab tak saaf na ho, repo ke root mein ek khaali file banao, naam: STOP_POSTER (GitHub → Add file → Create new file). Isse poster ruk jayega.",
                                "Warning hat jaye to STOP_POSTER file delete kar do. Machine ye file kabhi khud nahi banati ya hatati."],
                               f"{p.get('title', '?')} ({nice})"))
        elif rx.search(err):
            if pid == "META_TOKEN":
                out.append(Problem("META_TOKEN", "Facebook / Instagram ka token expire ya galat hai",
                                   "Facebook ya Instagram par post nahi ho raha. YouTube par koi asar nahi.",
                                   ["Meta developer account mein login karo → Tools → Graph API Explorer → apna Page chuno → naya Page access token banao (wahi permissions jo pehle the).",
                                    "GitHub repo → Settings → Secrets and variables → Actions → secret ka naam META_PAGE_TOKEN → Update secret → naya token daalo.",
                                    "Token kabhi chat, issue ya comment mein paste mat karna.",
                                    "GitHub → Actions tab → 'DASHX Meta Check' → Run workflow. Ye sirf check hai, kuch post nahi karta.",
                                    "Check green ho jaye to ye alert apne aap band ho jayega."],
                                   f"{p.get('title', '?')} ({nice})"))
            else:
                out.append(Problem("YT_TOKEN", "YouTube ka login (token) kharab ya missing hai",
                                   "YouTube upload nahi ho raha. Facebook aur Instagram alag chalte hain.",
                                   ["GitHub repo → Settings → Secrets and variables → Actions → in 3 secrets ko dekho: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN.",
                                    "Google Cloud Console mein wahi OAuth client kholo jo pehle YouTube setup mein banaya tha, aur naya refresh token banao.",
                                    "YT_REFRESH_TOKEN secret ko Update karo. Value kisi ko mat dikhana.",
                                    "Agle poster run mein upload chal jayega aur ye alert band ho jayega."],
                                   f"{p.get('title', '?')} ({nice})"))
    # Gemini key invalid / refill silent
    m = re.search(r"Story refill (\d{4}-\d\d-\d\d)", s.refill_daily)
    refill_day = datetime.fromisoformat(m.group(1)).date() if m else None
    if GEMINI_RE.search(s.refill_daily) and refill_day and (s.now.date() - refill_day).days <= 3:
        out.append(Problem("GEMINI_KEY", "Gemini key kaam nahi kar rahi (nayi kahaniyan nahi ban rahi)",
                           "Story Refill ko Gemini se 400/401/403 jawab mila: key galat, band ya limit se bahar hai. Purani kahaniyan chalti rahengi, par naye nahi bante.",
                           ["aistudio.google.com/apikey kholo → free key banao ya purani check karo.",
                            "GitHub repo → Settings → Secrets and variables → Actions → secret ka naam GEMINI_API_KEY → Update secret.",
                            "Key kabhi chat ya issue mein paste mat karna.",
                            "GitHub → Actions tab → 'DASHX Story Refill' → Run workflow (dry_run ON rakho) → log mein 'accepted' dikhna chahiye.",
                            "Sab theek hone par ye alert apne aap band ho jayega."], "Story Refill"))
    elif refill_day and (s.now.date() - refill_day).days > 3:
        out.append(Problem("GEMINI_KEY", "Story Refill 3 din se chupchap hai (key missing ho sakti hai)",
                           f"Aakhri refill report {refill_day.isoformat()} ki hai. Key hat gayi ho ya workflow band ho sakta hai.",
                           ["GitHub repo → Settings → Secrets and variables → Actions → check karo GEMINI_API_KEY maujood hai.",
                            "GitHub → Actions tab → 'DASHX Story Refill' → dekho koi STOP_REFILL file ya band schedule to nahi.",
                            "Run workflow se ek baar chalao (dry_run ON). Report aate hi alert band ho jayega."], "Story Refill"))
    streak = int((s.refill_errors or {}).get("streak", 0) or 0)
    if streak >= REFILL_ERR_DAYS and refill_day and (s.now.date() - refill_day).days <= 3 and not GEMINI_RE.search(s.refill_daily):
        out.append(Problem("REFILL_ERRORS", f"Story Refill {streak} din se Gemini errors par ruk raha hai",
                           f"Lagatar {streak} refill din: grading ya likhna Gemini ke server/network error (HTTP 0 ya 5xx) par ruka. Purani kahaniyan chalti rahengi, "
                           "par naye stories grade ya likhe nahi ja rahe, aur roz ke Gemini calls bekaar ja rahe hain. Key galat hone ka error (400/401/403) ye nahi hai.",
                           ["GitHub → Actions → 'DASHX Story Refill' → latest run → 'Write the daily stories' step kholo aur dekho kaun sa HTTP code aaya (503, 500, 0...).",
                            "503 / 500 = Gemini ka server busy. Kuch karna nahi, agle din apne aap theek ho sakta hai.",
                            "0 / timeout = network. Agar 3 din se zyada chale to aistudio.google.com/apikey par key aur quota check karo.",
                            "Key kabhi chat ya issue mein paste mat karna.",
                            "Jis din refill bina error ke chalega, ye alert apne aap band ho jayega."],
                           f"refill {refill_day.isoformat()}"))
    lm = re.search(r"(\d+) stories left", s.refill_daily)
    if lm and int(lm.group(1)) < LOW_STOCK:
        n = int(lm.group(1))
        crit = n < CRITICAL_STOCK
        out.append(Problem("STORY_BANK_CRITICAL" if crit else "STORY_BANK_LOW",
                           (f"STORY BANK BAHUT KAM HAI: sirf {n} kahaniyan bachi hain" if crit else f"Story bank kam ho raha hai: {n} kahaniyan bachi hain"),
                           (f"Roz 2 reels banti hain, to ye bank sirf {n // 2} din chalega. Posting nahi rukegi aur machine schedule ya reels ki ginti nahi badlegi, par naye stories jaldi chahiye."
                            if crit else f"Roz 2 reels banti hain, to ye bank {n // 2} din chalega. Story Refill roz naye stories jodta hai; agar wo fail ho raha hai to bank kam hota jayega."),
                           ["GitHub → Actions → 'DASHX Story Refill' → latest run → 'Write the daily stories' step kholo aur dekho kya error hai (network, key ya quota).",
                            "status/daily.md mein 'Story bank and Gemini quota' dekho: kitne Gemini calls use hue.",
                            "Gemini key ka haal: aistudio.google.com/apikey. Agar key theek hai to Actions → 'DASHX Story Refill' → Run workflow (dry_run OFF) se ek baar chalao.",
                            "Ye alert tab band hoga jab bank 12 ya usse upar ho jaye."],
                           f"{n} stories left"))
    if not s.rules_ok:
        out.append(Problem("RULES_TAMPERED", "Autonomy ki rule file badli hui hai, machine ruk gayi hai",
                           "autonomy/RULES.json seal se match nahi karti. Jab tak tum ya koi check na kare, machine kuch nahi badlegi.",
                           ["Agar rule file tumne khud badli: apne PC par `python autonomy/guard.py seal` chalao aur naya autonomy/RULES.sha256 commit karo.",
                            "Agar tumne nahi badli: GitHub → autonomy/RULES.json → History dekho aur galat badlav wapas karo.",
                            "Tab tak chahe to repo root mein STOP_AUTONOMY file bana do."], "autonomy/RULES.json"))
    if s.watch.get("status") in ("revert_failed", "revert_refused"):
        out.append(Problem("REVERT_STUCK", "Machine apna ek badlav wapas nahi le paayi",
                           "Ek self-change ke baad nayi dikkat dikhi, par auto-revert poora nahi hua. Badla hua file abhi main mein hai.",
                           ["GitHub repo → autonomy/log.md kholo, 'auto_revert' wali line padho.",
                            f"autonomy/watch.json mein dekho kaun si file badli thi ({', '.join(s.watch.get('files', [])[:3]) or 'file ka naam wahan likha hai'}).",
                            "GitHub → Commits mein 'Autonomy self-improvement merged' wala commit dhundo → Revert dabao.",
                            "Revert ho jaye to watch.json ka status 'reverted' kar do ya file delete kar do."], s.watch.get("idea", "")))
    until = ladder._t(s.ladder.get("drop_alert_until")) if isinstance(s.ladder, dict) else None
    if until and until > s.now:
        out.append(Problem("LADDER_DROP", "Machine ek Trust Ladder step neeche aa gayi",
                           "Ek reel slot chhoot gaya, Meta warning jaisa kuch dikha, ya ek self-change ke baad reel kharab hui. Isliye machine ne ek step kam kar diya aur bharosa dobara kamana shuru kiya. Kuch toot nahi gaya, bas machine zyada savdhaan hai.",
                           ["status/daily.md kholo: 'Trust Ladder' hissa batata hai kaun sa step hai aur kya hua.",
                            "autonomy/log.md mein 'ladder | drop' wali line padho.",
                            "Agar Meta warning thi: Facebook / Instagram app mein Account status dekho. Gadbad ho toh repo root mein STOP_POSTER file banao.",
                            "Agar sab theek lage: kuch karna nahi. Ye alert 7 din baad apne aap band ho jayega.",
                            "Agar baar baar aaye: GitHub → Settings → Variables mein DASHX_AUTONOMY_ENABLED ko false kar do aur Claude ko batao."],
                           str(s.ladder.get("last_drop", ""))[:160]))
    if not s.ladder_ok and s.rules_ok:
        out.append(Problem("LADDER_FILE", "TRUST_LADDER.md badli hui hai, machine step 1 par ruki hai",
                           "autonomy/TRUST_LADDER.md RULES.json mein sealed hash se match nahi karti. Jab tak tum na check karo, machine sirf dekhti rahegi (self-improvement band).",
                           ["Agar file tumne khud badli: apne PC par RULES.json mein uska naya hash daalo aur `python autonomy/guard.py seal` chalao.",
                            "Agar tumne nahi badli: GitHub → autonomy/TRUST_LADDER.md → History dekho aur galat badlav wapas karo."], "autonomy/TRUST_LADDER.md"))
    # one entry per id (several networks can raise the same one)
    seen, uniq = set(), []
    for p in out:
        if p.id not in seen:
            seen.add(p.id)
            uniq.append(p)
        else:
            first = next(x for x in uniq if x.id == p.id)
            if p.evidence and p.evidence not in first.evidence:
                first.evidence += f"; {p.evidence}"
    return uniq


# ---------------------------------------------------------------- the issue text
def render_body(problems: list[Problem], now: datetime) -> str:
    lines = ["# DASHX ALERT", "",
             "Machine khud ye theek nahi kar sakti. Neeche likha hai kya karna hai. Sab kuch GitHub ke andar hi ho jata hai, koi paisa ya naya service nahi.", ""]
    for i, p in enumerate(problems, 1):
        lines += [f"## {i}. {p.title}", p.what, ""]
        if p.evidence:
            lines += [f"Kahan dikha: {p.evidence}", ""]
        lines += ["Kya karna hai:"] + [f"{n}. {step}" for n, step in enumerate(p.steps, 1)] + [""]
    lines += ["---", "Ye issue apne aap band ho jayega jab sab theek ho jayega. Naya issue mat banao, isi mein update aata rahega.",
              f"Aakhri check: {now.strftime('%d %b %Y %H:%M')} IST", ""]
    body = "\n".join(lines)
    h = hashlib.sha256("|".join(f"{p.id}:{p.evidence}" for p in problems).encode()).hexdigest()[:12]
    return body + f"<!-- dashx-alert:{h} -->\n"


def body_hash(body: str) -> str:
    m = re.search(r"<!-- dashx-alert:(\w+) -->", body or "")
    return m.group(1) if m else ""


# ---------------------------------------------------------------- GitHub Issues (the job's own GITHUB_TOKEN, permission issues: write)
class Issues:
    def __init__(self, repo: str | None = None, token: str | None = None):
        self.repo = repo or os.environ.get("GITHUB_REPOSITORY", "")
        self._tok = token or os.environ.get("GITHUB_TOKEN", "")

    def _req(self, method: str, path: str, body: dict | None = None):
        req = urllib.request.Request(f"https://api.github.com/repos/{self.repo}{path}", method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": f"Bearer {self._tok}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}

    def open_alerts(self) -> list[dict]:
        j = self._req("GET", "/issues?state=open&per_page=100")
        return sorted([i for i in j if i.get("title") == TITLE and "pull_request" not in i], key=lambda i: i["number"])

    def create(self, body: str) -> int:
        return self._req("POST", "/issues", {"title": TITLE, "body": body, "labels": [LABEL]})["number"]

    def update(self, n: int, body: str) -> None:
        self._req("PATCH", f"/issues/{n}", {"body": body})

    def comment(self, n: int, text: str) -> None:
        self._req("POST", f"/issues/{n}/comments", {"body": text})

    def close(self, n: int) -> None:
        self._req("PATCH", f"/issues/{n}", {"state": "closed", "state_reason": "completed"})


def sync_issue(api, problems: list[Problem], now: datetime) -> str:
    """ONE open issue. Returns what happened: created / updated / unchanged / closed / none."""
    open_ = api.open_alerts()
    keep, extra = (open_[0], open_[1:]) if open_ else (None, [])
    for e in extra:                                              # no duplicates: close the later ones
        api.comment(e["number"], "Duplicate: sirf ek DASHX ALERT issue chalta hai (pehla wala).")
        api.close(e["number"])
    if not problems:
        if keep:
            api.comment(keep["number"], f"Sab theek ho gaya ({now.strftime('%d %b %H:%M')} IST). Issue band.")
            api.close(keep["number"])
            return "closed"
        return "none"
    body = render_body(problems, now)
    if not keep:
        api.create(body)
        return "created"
    if body_hash(keep.get("body", "")) == body_hash(body):
        return "unchanged"                                       # same problems: no noise
    api.update(keep["number"], body)
    return "updated"


# ---------------------------------------------------------------- status for the /status/ page
def level(s: Signals, problems: list[Problem]) -> tuple[str, list[str]]:
    if problems:
        return "red", [p.title for p in problems]
    y = []
    if s.stops:
        y.append("paused by " + ", ".join(s.stops))
    m = re.search(r"(\d+) stories left", s.refill_daily)
    if m and int(m.group(1)) <= 6:
        y.append(f"story bank is low ({m.group(1)} left)")
    cap, calls = int(s.usage.get("cap", 12) or 12), int(s.usage.get("calls", 0) or 0)
    if s.usage.get("day") and calls >= cap and "calls used" in s.refill_daily and "limit" in s.refill_daily:
        y.append("Gemini calls used up for today")
    if s.watch.get("status") == "watching":
        y.append(f"watching a self-change: {s.watch.get('idea', '')}")
    if any(f"| report | {k} |" in s.log_text and s.now.strftime("%Y-%m-%d") in ln for ln in s.log_text.splitlines() for k in ("poster_runs_failing", "poster_redispatch_limit", "duplicate_guard")):
        y.append("the heal check reported something today (see autonomy/log.md)")
    if any("auto_revert" in ln and (s.now - datetime.strptime(ln[2:18], "%Y-%m-%d %H:%M").replace(tzinfo=IST)) < timedelta(days=3)
           for ln in s.log_text.splitlines() if ln.startswith("- ") and len(ln) > 20):
        y.append("a self-change was reverted in the last 3 days")
    if s.learning.get("availability") and any(str(v).startswith("DENIED") for v in s.learning["availability"].values()):
        y.append("a stats source needs your decision (see the daily report)")
    return ("yellow", y) if y else ("green", [])


def status_json(s: Signals, problems: list[Problem]) -> dict:
    lv, why = level(s, problems)
    topics = [t for t in s.trends.get("topics", []) if str(t.get("expires", "")) >= s.now.date().isoformat()]
    trend = {"topic": topics[0]["topic"], "angle": topics[0].get("story_angle", "")[:160]} if topics else None
    return {"level": lv, "reasons": why[:5], "alerts": len(problems), "trend": trend, "ladder": s.ladder or ladder.new_state(),
            "refill_errors": s.refill_errors or {}, "updated": s.now.isoformat(timespec="minutes")}


def write_status(root: Path, data: dict) -> None:
    rel = "autonomy/status.json"
    assert rel in ALLOWED_OUT
    try:   # unchanged for under 2 hours: do not write (no commit every 30 minutes)
        cur = json.loads((root / rel).read_text(encoding="utf-8"))
        same = all(cur.get(k) == data.get(k) for k in ("level", "reasons", "alerts", "trend", "ladder", "refill_errors"))
        if same and datetime.fromisoformat(data["updated"]) - datetime.fromisoformat(cur["updated"]) < timedelta(hours=2):
            return
    except Exception:
        pass
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def run(root: Path = ROOT, now: datetime | None = None, api=None) -> dict:
    s = load_signals(root, now)
    if guard.halted("all", root):
        print(f"{guard.halted('all', root)} is on: alerts do nothing")
        return {"halted": True}
    if s.rules_ok:                                           # the Trust Ladder moves (or drops) first, so a drop raises its alert in this very run
        s.ladder, lines = ladder.evaluate(s.ladder, s.posts, s.log_text, s.learning, s.now, s.rules_ok, s.ladder_ok, s.ladder_why)
        ladder.write_log(root, lines)
    s.refill_errors = refill_streak(s.refill_errors, s.refill_daily)
    problems = detect(s)
    result = sync_issue(api or Issues(), problems, s.now) if (api or os.environ.get("GITHUB_TOKEN")) else "no token: issue not touched"
    st = status_json(s, problems)
    write_status(root, st)
    out = {"problems": [p.id for p in problems], "issue": result, "level": st["level"]}
    try:   # the 21:00 IST report cron is often hours late or skipped: every alerts run also writes the report when it is due
        import report  # noqa: PLC0415  (report imports this module)
        if report.due(root, s.now):
            out["report"] = report.run(root, s.now)
    except Exception as e:
        out["report_error"] = type(e).__name__
    return out


if __name__ == "__main__":
    out = run()
    print("alerts:", out)
    sys.exit(1 if out.get("level") == "red" and "RULES_TAMPERED" in out.get("problems", []) else 0)
