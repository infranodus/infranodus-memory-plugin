#!/usr/bin/env python3
"""Collect extraction results into out/summary.md (tables) and out/review.md
(every statement, grouped by session, for hand-checking)."""
import collections
import glob
import json
import os
import re

os.chdir(os.path.dirname(os.path.abspath(__file__)))
DIARY = re.compile(r"(?i)\b(the user (asked|wanted|requested)|today|in this session|the agent (fixed|did|added)|we (fixed|added|did))\b")

rows, review = [], collections.defaultdict(list)
for f in sorted(glob.glob("out/results/*.json")):
    base = os.path.basename(f)[:-5]
    excerpt, model = base.rsplit(".", 1)
    num, rest = excerpt.split("-", 1)
    session, mode = rest.rsplit("-", 1)
    try:
        meta = json.load(open(f))
        if isinstance(meta, list):
            meta = next((e for e in meta if e.get("type") == "result"), {})
        text = meta.get("result", "")
        m = re.search(r"\[.*\]", text, re.S)
        raw = m.group(0) if m else "[]"
        try:
            items, ok = json.loads(raw), True
        except ValueError:
            items, ok = json.loads(raw.replace('","}', '"}')), "repaired"
    except Exception as e:  # noqa: BLE001
        meta, items, ok = {}, [], False
    usage = meta.get("usage", {}) or {}
    in_tok = usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
    kinds = collections.Counter(i.get("kind") for i in items)
    links = [len(re.findall(r"\[\[", i.get("statement", ""))) for i in items]
    diary = sum(bool(DIARY.search(i.get("statement", ""))) for i in items)
    rows.append({
        "n": int(num), "session": session, "mode": mode, "model": model, "ok": ok,
        "items": len(items), "learning": kinds.get("learning", 0), "personal": kinds.get("personal", 0),
        "topic": kinds.get("topic", 0), "diary": diary,
        "no_link": sum(1 for x in links if x == 0),
        "in_tok": in_tok, "cost": meta.get("total_cost_usd", 0) or 0,
        "secs": round((meta.get("duration_ms", 0) or 0) / 1000),
    })
    review[(int(num), session)].append((mode, model, items))

rows.sort(key=lambda r: (r["n"], r["mode"] != "trimmed", r["model"]))
with open("out/summary.md", "w") as s:
    s.write("| # | session | mode | model | items | learn | pers | topic | diary? | no [[ ]] | input tok | cost $ | s |\n|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
    for r in rows:
        s.write(f"| {r['n']} | {r['session']} | {r['mode']} | {r['model']} | {r['items'] if r['ok'] is True else (str(r['items'])+'*' if r['ok'] else 'ERR')} | {r['learning']} | {r['personal']} | {r['topic']} | {r['diary']} | {r['no_link']} | {r['in_tok']:,} | {r['cost']:.3f} | {r['secs']} |\n")
    agg = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        k = (r["mode"], r["model"])
        for f in ("items", "learning", "personal", "topic", "diary", "no_link", "in_tok", "secs"):
            agg[k][f] += r[f]
        agg[k]["cost"] += r["cost"]
        agg[k]["runs"] += 1
    s.write("\n| mode | model | runs | items | personal | topic | diary? | avg input tok | total cost $ | avg s |\n|---|---|---:|---:|---:|---:|---:|---:|---:|---:|\n")
    for (mode, model), a in sorted(agg.items()):
        s.write(f"| {mode} | {model} | {a['runs']} | {a['items']} | {a['personal']} | {a['topic']} | {a['diary']} | {a['in_tok'] // max(a['runs'], 1):,} | {a['cost']:.2f} | {a['secs'] // max(a['runs'], 1)} |\n")

with open("out/review.md", "w") as r:
    for (num, session), runs in sorted(review.items()):
        r.write(f"\n# {num}. {session}\n")
        for mode, model, items in sorted(runs, key=lambda x: (x[0] != "trimmed", x[1])):
            r.write(f"\n## {mode} / {model} ({len(items)})\n\n")
            for i in items:
                r.write(f"- [{i.get('kind')}/{i.get('type')}] {i.get('statement')}\n")
print(open("out/summary.md").read())
