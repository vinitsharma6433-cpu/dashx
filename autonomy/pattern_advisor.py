"""DASHX Pattern Advisor: the 'advanced level' of the Pattern Analyzer. Stdlib only, pure functions.

Turns weekly niche patterns + our own reel results into a small number of EXPERIMENTS:
  history -> trend detection -> gap vs our own reels -> proposals (fixed sentences only)
  -> later: evaluate each experiment against real views and keep / drop / mutate / wait.

Safety by design:
- Inputs are aggregates (enums and numbers). Outputs are fixed template sentences + enums.
  Nothing from any source text can appear in a proposal.
- It only PROPOSES. Applying goes through guard.py, the 1-change-a-day limit, the 2-reel watch
  and auto-revert, exactly like Scout. This module never writes files or calls a network.
- A dropped idea is quarantined (BLOCK_DAYS).

INTEGRATION CHANGES to the owner's version (reported to the owner): HISTORY_WEEKS 8 -> 12 and BLOCK_DAYS 14 -> 21 (owner's new spec),
FIELDS = the 7-tag genome, new functions for our own genome stats (decay, 2-way and 3-way combinations, UCB1, KEEP / DROP / MUTATE / WAIT,
the 80/20 blueprint, the weekly brief, the retention diagnostics of phase 2). The owner's functions are unchanged.
"""
import datetime
import math
import random

HISTORY_WEEKS = 12         # rolling window
MAX_PROPOSALS_PER_WEEK = 2
MIN_SOURCES = 3            # niche sample must have at least this many sources
MIN_NICHE_SHARE = 0.5      # a pattern must be in at least half of the niche sources
MAX_OWN_SHARE = 0.3        # ...and we must use it in less than 30% of our reels
MIN_TAGGED_REELS = 3       # reels needed before a pattern can be judged (N >= 3)
KEEP_LIFT = 1.2
DROP_LIFT = 0.8
BLOCK_DAYS = 21            # quarantine of a dropped pattern
TREND_RISE = 0.2           # share must rise by 20 points over the last two weeks
HALF_LIFE_WEEKS = 4.0      # exponential time decay: a result 4 weeks old weighs half
THREE_WAY_MIN_REELS = 60   # 3-way combinations only with at least this many tagged reels
MAX_EXPERIMENTS = 2        # micro-experiments per week (the 20% share)
WEEKLY_STORIES = 14        # 2 reels a day
BRIEF_MAX_LINES = 15

FIELDS = ("hook_type", "first_3s", "emotion", "structure", "pacing_bucket", "ending_loop", "shareable_because")

# Fixed sentences. {v} is always an enum value, never free text.
TEMPLATES = {
    "hook_type": "Try the hook type '{v}' in about 1 of 5 new stories.",
    "first_3s": "Try opening with '{v}' in the first 3 seconds in about 1 of 5 new reels.",
    "emotion": "Try the emotion '{v}' as the main feeling in about 1 of 5 new stories.",
    "structure": "Try the story structure '{v}' in about 1 of 5 new stories.",
    "pacing_bucket": "Try the pacing '{v}' in about 1 of 5 new reels.",
    "ending_loop": "Try the ending '{v}' in about 1 of 5 new reels.",
    "shareable_because": "Add a '{v}' share trigger to the end of about 1 of 5 new reels.",
}


# ====================================================================================== the owner's functions (unchanged)
def update_history(history, agg, weeks=HISTORY_WEEKS):
    """Append this week's aggregate (from pattern_analyzer.aggregate). Keeps the last `weeks`.
    Replaces an entry with the same date. Returns a new list."""
    hist = [h for h in (history or []) if h.get("generated") != agg.get("generated")]
    hist.append({"generated": agg.get("generated"), "sources_analysed": agg.get("sources_analysed", 0),
                 "counts": agg.get("counts", {})})
    hist.sort(key=lambda h: h.get("generated") or "")
    return hist[-weeks:]


def _share(entry, field, value):
    counts = (entry.get("counts") or {}).get(field) or {}
    total = sum(counts.values())
    return (counts.get(value, 0) / total) if total else 0.0


def rising_patterns(history, fields=FIELDS):
    """Values whose share in the niche rose by >= TREND_RISE across the last two entries."""
    if len(history or []) < 2:
        return []
    prev, last = history[-2], history[-1]
    out = []
    for f in fields:
        for v in (last.get("counts", {}).get(f) or {}):
            rise = _share(last, f, v) - _share(prev, f, v)
            if rise >= TREND_RISE:
                out.append({"field": f, "value": v, "rise": round(rise, 2)})
    return sorted(out, key=lambda r: (-r["rise"], r["field"], r["value"]))


def own_share(rows, field, value):
    """Share of our reels (that have this field) using this value. None when we have no data."""
    tagged = [r for r in rows if r.get(field)]
    if not tagged:
        return None
    return sum(1 for r in tagged if r[field] == value) / len(tagged)


def is_blocked(blocked, field, value, today=None):
    today = today or datetime.date.today()
    for b in blocked or []:
        if b.get("field") == field and b.get("value") == value:
            until = datetime.date.fromisoformat(b["until"])
            if today <= until:
                return True
    return False


def propose_experiments(agg, own_rows, history=None, blocked=None, today=None, limit=MAX_PROPOSALS_PER_WEEK):
    """Return at most `limit` experiments. Sample too small -> no proposals at all."""
    today = today or datetime.date.today()
    if (agg or {}).get("sources_analysed", 0) < MIN_SOURCES:
        return []
    rising = {(r["field"], r["value"]) for r in rising_patterns(history or [])}
    n = agg["sources_analysed"]
    cands = []
    for f in FIELDS:
        counts = (agg.get("counts") or {}).get(f) or {}
        for v, c in counts.items():
            if v in ("none", "other"):
                continue
            niche = c / n
            if niche < MIN_NICHE_SHARE:
                continue
            if is_blocked(blocked, f, v, today):
                continue
            ours = own_share(own_rows or [], f, v)
            if ours is not None and ours >= MAX_OWN_SHARE:
                continue
            score = niche + (0.2 if (f, v) in rising else 0.0)
            cands.append({
                "id": f"{f}:{v}:{today.isoformat()}",
                "field": f, "value": v,
                "niche_share": round(niche, 2),
                "own_share": None if ours is None else round(ours, 2),
                "confidence": "medium" if ours is not None else "low (no own data for this field)",
                "rising": (f, v) in rising,
                "proposal": TEMPLATES[f].format(v=v),
                "_score": score,
            })
    cands.sort(key=lambda c: (-c["_score"], c["field"], c["value"]))
    out = []
    for c in cands[:limit]:
        c = dict(c)
        c.pop("_score")
        out.append(c)
    return out


def evaluate_experiment(exp, own_rows, today=None):
    """Judge an experiment from real reels. Rows need 'views_per_day' and the tagged field.
    Returns {'verdict': keep|drop|wait, 'lift': float|None, 'tagged': n, 'block': {...}|None}."""
    today = today or datetime.date.today()
    f, v = exp["field"], exp["value"]
    tagged = [r["views_per_day"] for r in own_rows if r.get(f) == v and r.get("views_per_day") is not None]
    other = [r["views_per_day"] for r in own_rows if r.get(f) not in (None, v) and r.get("views_per_day") is not None]
    if len(tagged) < MIN_TAGGED_REELS or not other:
        return {"verdict": "wait", "lift": None, "tagged": len(tagged), "block": None}
    mean_t = sum(tagged) / len(tagged)
    mean_o = sum(other) / len(other)
    if mean_o <= 0:
        return {"verdict": "wait", "lift": None, "tagged": len(tagged), "block": None}
    lift = round(mean_t / mean_o, 2)
    if lift >= KEEP_LIFT:
        return {"verdict": "keep", "lift": lift, "tagged": len(tagged), "block": None}
    if lift <= DROP_LIFT:
        until = (today + datetime.timedelta(days=BLOCK_DAYS)).isoformat()
        return {"verdict": "drop", "lift": lift, "tagged": len(tagged),
                "block": {"field": f, "value": v, "until": until}}
    return {"verdict": "wait", "lift": lift, "tagged": len(tagged), "block": None}


def report_block(proposals, rising):
    """Short text for status/daily.md."""
    lines = ["## Niche experiments (proposals only, nothing applied)"]
    if not proposals:
        lines.append("No experiment proposed this week (not enough data or already covered).")
    for p in proposals:
        lines.append(f"- {p['proposal']} (niche share {p['niche_share']}, ours {p['own_share']}, {p['confidence']})")
    if rising:
        top = ", ".join(f"{r['field']}={r['value']}" for r in rising[:3])
        lines.append(f"- Rising in the niche: {top}")
    return "\n".join(lines) + "\n"


# ====================================================================================== our own genome stats
def week_tag(day):
    y, w, _ = day.isocalendar()
    return f"{y}-W{w:02d}"


def week_index(tag):
    """'2026-W47' -> a number that grows by 1 per week (for the decay)."""
    y, w = tag.split("-W")
    return int(y) * 53 + int(w)


def pattern_keys(tags, max_k=2):
    """'field=value' for every tag, 'f1=v1+f2=v2' for every pair, and triples when max_k == 3. Fields in genome order."""
    items = [f"{f}={tags[f]}" for f in FIELDS if tags.get(f)]
    keys = list(items)
    if max_k >= 2:
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                keys.append(items[i] + "+" + items[j])
    if max_k >= 3:
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                for k in range(j + 1, len(items)):
                    keys.append(items[i] + "+" + items[j] + "+" + items[k])
    return keys


def reel_scores(rows, w_views=0.7, w_react=0.3):
    """Composite score per reel from views_per_day and reactions_per_day, relative to the median of THIS batch (100 = typical reel)."""
    def med(xs):
        xs = sorted(xs)
        return xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2 if xs else 0

    mv = med([r.get("views_per_day") or 0 for r in rows])
    mr = med([r.get("reactions_per_day") or 0 for r in rows])

    def rel(x, m):
        return 1.0 if m <= 0 else min(3.0, (x or 0) / m)
    return [round(100 * (w_views * rel(r.get("views_per_day"), mv) + w_react * rel(r.get("reactions_per_day"), mr)), 1) for r in rows]


def week_stats(rows, scores, max_k):
    """{'reels','tagged','all':{n,sum},'pat':{key:{n,sum}}} for the reels of ONE week. Only counts, sums and enum keys: no title."""
    out = {"reels": len(rows), "tagged": 0, "all": {"n": 0, "sum": 0.0}, "pat": {}}
    for r, s in zip(rows, scores):
        out["all"]["n"] += 1
        out["all"]["sum"] += s
        tags = {f: r["tags"][f] for f in FIELDS if (r.get("tags") or {}).get(f)}
        if tags:
            out["tagged"] += 1
        for key in pattern_keys(tags, max_k):
            p = out["pat"].setdefault(key, {"n": 0, "sum": 0.0})
            p["n"] += 1
            p["sum"] += s
    out["all"]["sum"] = round(out["all"]["sum"], 2)
    for p in out["pat"].values():
        p["sum"] = round(p["sum"], 2)
    return out


def update_own_history(own, week, stats, weeks=HISTORY_WEEKS):
    """own = list of {'week', 'stats'}. Replaces the same week, keeps the last `weeks` weeks."""
    h = [e for e in (own or []) if e.get("week") != week]
    h.append({"week": week, "stats": stats})
    h.sort(key=lambda e: week_index(e["week"]))
    return h[-weeks:]


def combine(own, now_week, half_life=HALF_LIFE_WEEKS):
    """Decayed totals over the window. Returns {'all': (wn, wsum, n), 'pat': {key: (wn, wsum, n)}} where wn/wsum are weighted."""
    now_i = week_index(now_week)
    tot = {"all": [0.0, 0.0, 0], "pat": {}}
    for e in own or []:
        w = 0.5 ** (max(0, now_i - week_index(e["week"])) / half_life)
        s = e["stats"]
        tot["all"][0] += w * s["all"]["n"]
        tot["all"][1] += w * s["all"]["sum"]
        tot["all"][2] += s["all"]["n"]
        for k, p in s["pat"].items():
            a = tot["pat"].setdefault(k, [0.0, 0.0, 0])
            a[0] += w * p["n"]
            a[1] += w * p["sum"]
            a[2] += p["n"]
    return tot


def tagged_total(own):
    return sum(e["stats"].get("tagged", 0) for e in own or [])


def lifts(own, now_week, today=None, quarantine=None):
    """Per pattern: raw n, decayed mean, baseline (decayed mean of the reels WITHOUT the pattern) and lift. Deterministic."""
    tot = combine(own, now_week)
    all_wn, all_ws, all_n = tot["all"]
    out = {}
    for k, (wn, ws, n) in tot["pat"].items():
        base_n, base_s = all_wn - wn, all_ws - ws
        mean = ws / wn if wn > 0 else 0.0
        base = base_s / base_n if base_n > 1e-9 else None
        lift = round(mean / base, 2) if base and base > 0 else None
        out[k] = {"n": n, "mean": round(mean, 1), "baseline": None if base is None else round(base, 1), "lift": lift}
    return out


def decide(key, st, quarantined=False):
    """KEEP / DROP / WAIT for one pattern (MUTATE is decided in mutations())."""
    if quarantined:
        return "quarantined"
    if st["n"] < MIN_TAGGED_REELS or st["lift"] is None:
        return "wait"
    if st["lift"] >= KEEP_LIFT:
        return "keep"
    if st["lift"] <= DROP_LIFT:
        return "drop"
    return "wait"


def quarantine_entry(key, today):
    return {"key": key, "until": (today + datetime.timedelta(days=BLOCK_DAYS)).isoformat()}


def is_quarantined(quarantine, key, today):
    return any(q.get("key") == key and today <= datetime.date.fromisoformat(q["until"]) for q in quarantine or [])


def mutations(verdicts, stats, quarantine, today):
    """MUTATE: a combination that pairs a good hook with an ending that failed. Keep the hook, suggest ANOTHER ending_loop."""
    out = []
    for k, v in sorted(verdicts.items()):
        if v != "drop" or "ending_loop=" not in k or k.count("+") != 1:
            continue
        a, b = k.split("+")
        hook, end = (a, b) if b.startswith("ending_loop=") else (b, a)
        if not hook.startswith("hook_type="):
            continue
        hs = stats.get(hook)
        if not hs or hs["n"] < MIN_TAGGED_REELS or (hs["lift"] or 0) < 1.0:
            continue
        others = [f"ending_loop={x}" for x in ("seamless_audio_loop", "cliffhanger_part2", "punchline_freeze") if f"ending_loop={x}" != end
                  and not is_quarantined(quarantine, f"ending_loop={x}", today) and not is_quarantined(quarantine, f"{hook}+ending_loop={x}", today)]
        if others:
            out.append({"keep": hook, "drop_ending": end, "try": others[0]})
    return out


def ucb1(mean_rel, n, total_n):
    """UCB1 for one arm: mean relative reward + sqrt(2 ln N / n). Unseen arm (n == 0): infinite."""
    if n <= 0:
        return float("inf")
    return mean_rel + math.sqrt(2.0 * math.log(max(total_n, 2)) / n)


def blueprint(own, now_week, enums, today, quarantine=None, niche_proposals=None, stories=WEEKLY_STORIES, max_experiments=MAX_EXPERIMENTS):
    """Next week's 80/20 plan. Deterministic: ties between equal arms are broken by a shuffle seeded with the ISO week number.
    Returns {'proven': [{'key','lift','n'}], 'proven_stories': n, 'experiments': [{'key','why'}], 'experiment_stories': n, 'mutate': [...]}."""
    st = lifts(own, now_week)
    quarantine = quarantine or []
    verdicts = {k: decide(k, v, is_quarantined(quarantine, k, today)) for k, v in st.items()}
    seed = week_index(now_week)
    total_n = max(1, sum(v["n"] for k, v in st.items() if "+" not in k))
    all_mean = (lambda t: t[1] / t[0] if t[0] > 0 else 0.0)(combine(own, now_week)["all"][:2])
    # proven: patterns with the KEEP verdict, best lift first (single tags and 2-way combinations)
    proven = sorted([k for k, v in verdicts.items() if v == "keep"], key=lambda k: (-st[k]["lift"], k.count("+"), k))[:3]
    # exploration: arms with the highest UCB1 among all single enum values (unseen = infinite), niche-gap proposals first
    arms = []
    for f, vals in enums.items():
        for v in vals:
            k = f"{f}={v}"
            if is_quarantined(quarantine, k, today) or verdicts.get(k) in ("keep", "quarantined"):
                continue
            s = st.get(k)
            rel = (s["mean"] / all_mean) if (s and all_mean > 0) else 0.0
            arms.append((ucb1(rel, s["n"] if s else 0, total_n), k))
    rng = random.Random(seed)
    rng.shuffle(arms)                                           # seeded: the same week always gives the same order
    arms.sort(key=lambda a: -a[0] if a[0] != float("inf") else -1e18)
    exp = []
    for p in (niche_proposals or []):
        k = f"{p['field']}={p['value']}"
        if all(k != e["key"] for e in exp) and not is_quarantined(quarantine, k, today):
            exp.append({"key": k, "why": "common in the niche, rare in ours"})
    for u, k in arms:
        if len(exp) >= max_experiments:
            break
        if all(k != e["key"] for e in exp):
            exp.append({"key": k, "why": "never or rarely tried" if u == float("inf") else "highest upper confidence bound"})
    exp = exp[:max_experiments]
    n_exp = min(len(exp), max_experiments, max(0, round(stories * 0.2)))
    return {"proven": [{"key": k, "lift": st[k]["lift"], "n": st[k]["n"]} for k in proven], "proven_stories": stories - n_exp,
            "experiments": exp, "experiment_stories": n_exp, "mutate": mutations(verdicts, st, quarantine, today)}


def decision_report(own, now_week, today, quarantine=None):
    """verdict per pattern (keep / drop / wait / quarantined) + the new quarantine entries a DROP earns. Nothing is applied."""
    st = lifts(own, now_week)
    verdicts, newq = {}, []
    for k, v in st.items():
        q = is_quarantined(quarantine, k, today)
        verdicts[k] = decide(k, v, q)
        if verdicts[k] == "drop":
            newq.append(quarantine_entry(k, today))
    return st, verdicts, newq


def diag_zone(curve):
    """Phase 2. curve = [(seconds, percent_still_watching)]. Where do viewers leave? Returns 'hook_failure' (0-3 s), 'mid_story_boring' (4-15 s),
    'weak_ending' (after 15 s) or 'unknown'. The zone is the 3-second-or-wider step with the biggest loss."""
    pts = sorted((float(s), float(p)) for s, p in (curve or []))
    if len(pts) < 3:
        return "unknown"
    best, zone = 0.0, "unknown"
    for (s0, p0), (s1, p1) in zip(pts, pts[1:]):
        drop = p0 - p1
        if drop > best:
            best, zone = drop, ("hook_failure" if s1 <= 3 else "mid_story_boring" if s1 <= 15 else "weak_ending")
    return zone


def virality(row, medians):
    """Phase 2 virality score 0-100 from views_per_day, avg_percentage_viewed, shares_per_1k_views, sub_conversion_rate.
    A missing metric means: fall back to views_per_day only. Returns (score, mode) with mode 'full' or 'views_only'."""
    need = ("avg_percentage_viewed", "shares_per_1k_views", "sub_conversion_rate")
    if any(row.get(k) is None for k in need) or any(not medians.get(k) for k in ("views_per_day",) + need):
        return round(100 * min(3.0, (row.get("views_per_day") or 0) / max(medians.get("views_per_day") or 0, 1e-9)) / 3, 1), "views_only"

    def rel(k):
        return min(3.0, (row[k] if k != "views_per_day" else (row.get(k) or 0)) / medians[k])
    s = 0.4 * rel("views_per_day") + 0.3 * rel("avg_percentage_viewed") + 0.2 * rel("shares_per_1k_views") + 0.1 * rel("sub_conversion_rate")
    return round(100 * s / 3, 1), "full"


def brief_lines(data, bottom=None, max_lines=BRIEF_MAX_LINES):
    """The weekly block for status/daily.md (at most `max_lines` lines). Only enums, numbers and our own reel slugs given in `bottom`."""
    L = ["## Niche and genome brief (proposals only, nothing is applied)"]
    if not data:
        return L + ["No pattern study yet."]
    n_t = data.get("tagged_reels", 0)
    prov = (data.get("blueprint") or {}).get("proven") or []
    if prov:
        w = prov[0]
        L.append(f"- Top combo: {w['key']} (lift {w['lift']}x on {w['n']} reels, newer weeks count more).")
        L.append("- Why: it beat the average reel in the same window; each reel is scored from views and reactions per day.")
    else:
        L.append(f"- Top combo: none proven yet ({n_t} tagged reels; a pattern needs {MIN_TAGGED_REELS}+ reels and {KEEP_LIFT}x the average).")
    for b in (bottom or [])[:2]:
        L.append(f"- Weak reel {b['slug']} (score {b['score']}): likely weak part {b['part']}.")
    exps = data.get("experiments") or []
    for e in exps[:3]:
        L.append(f"- Experiment {e['key']}: n={e['n']}, lift {('%.0f%%' % ((e['lift'] - 1) * 100)) if e.get('lift') is not None else 'n/a'}, {e['status']}.")
    if not exps:
        L.append("- Active experiments: none with data yet.")
    bp = data.get("blueprint") or {}
    if bp:
        ex = ", ".join(e["key"] for e in bp.get("experiments", [])) or "none"
        L.append(f"- Next week 80/20: {bp.get('proven_stories', 0)} stories on proven combos or the normal mix, {bp.get('experiment_stories', 0)} micro-experiments: {ex}.")
        for m in bp.get("mutate", [])[:1]:
            L.append(f"- MUTATE: keep {m['keep']}, replace {m['drop_ending']} by {m['try']}.")
    if data.get("phase2") != "on":
        L.append("- Retention metrics are not available yet: scores use views and reactions per day (phase 2 is off).")
    L = L[:max_lines]
    return L
