"""Git merge driver for poster/queue.json (the factory appends entries while the poster updates results).
Called as: python poster/merge_queue.py BASE OURS THEIRS. Writes the merged JSON into OURS, exit 0 = merged.
Rules: entries are matched by (media, when). New entries from either side are kept. For a shared entry every network result
keeps the better one (ok beats not ok), notes are merged, status 'done' wins. Never loses a result, never drops an entry."""
import json
import sys


def load(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return {"posts": []}


def key(e):
    return (e.get("media"), e.get("when"))


def better(a, b):
    if a is None: return b
    if b is None: return a
    if bool(a.get("ok")) != bool(b.get("ok")): return a if a.get("ok") else b
    return a if str(a.get("at", "")) >= str(b.get("at", "")) else b


def merge_entry(o, t):
    m = dict(o)
    for k, v in t.items():
        if k not in m: m[k] = v
    res = {}
    for n in set(o.get("results", {})) | set(t.get("results", {})):
        res[n] = better(o.get("results", {}).get(n), t.get("results", {}).get(n))
    if res: m["results"] = res
    notes = dict(t.get("notes", {})); notes.update(o.get("notes", {}))
    for k in set(o.get("notes", {})) & set(t.get("notes", {})):   # flags: True wins; counters: bigger wins; lists: longer wins
        a, b = o["notes"][k], t["notes"][k]
        notes[k] = a if (a is True or (isinstance(a, (int, float)) and not isinstance(a, bool) and a >= b) or (isinstance(a, list) and len(a) >= len(b))) else b
    if notes: m["notes"] = notes
    if "done" in (o.get("status"), t.get("status")): m["status"] = "done"
    return m


def main():
    _, ours_p, theirs_p = sys.argv[1], sys.argv[2], sys.argv[3]
    ours, theirs = load(ours_p), load(theirs_p)
    t_by = {key(e): e for e in theirs.get("posts", [])}
    out, seen = [], set()
    for e in ours.get("posts", []):
        k = key(e); seen.add(k)
        out.append(merge_entry(e, t_by[k]) if k in t_by else e)
    for e in theirs.get("posts", []):
        if key(e) not in seen: out.append(e)
    merged = dict(ours); merged["posts"] = out
    json.dump(merged, open(ours_p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
