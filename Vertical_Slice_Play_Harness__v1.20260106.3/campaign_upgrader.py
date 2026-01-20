#!/usr/bin/env python3
"""campaign_upgrader.py

Upgrades Vertical Slice Play Harness scene_nodes JSONL files in-place style.

Goals (v0.4):
- Fix legacy rumor_pressure {"none": x} -> {"xi.faction.local": x}
- Inject milestone facts/locks to reduce "drift" feeling
- Add recurring event beats (nemesis/puzzle/revelation) via node["event"]
- Add minimal node-level ws_effects to support clocks / relief beats

This script is intentionally conservative:
- It DOES NOT add/remove nodes or rewrite next pointers.
- It preserves existing choice structure and text.
- It only adds fields or rewrites legacy rumor dict keys.

Usage:
  python campaign_upgrader.py --in RUN_001.scene_nodes.jsonl --out RUN_001_v0_4.scene_nodes.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any, Dict, Iterable, List, Tuple


NODE_RE = re.compile(r"^N(\d+)$")


def iter_jsonl(path: str) -> Iterable[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def write_jsonl(path: str, rows: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for obj in rows:
            f.write(json.dumps(obj, ensure_ascii=False))
            f.write("\n")


def node_number(node_id: str) -> int | None:
    m = NODE_RE.match(node_id)
    if not m:
        return None
    return int(m.group(1))


def _fix_legacy_rumor_in_mut(m: Dict[str, Any]) -> bool:
    """Return True if changed."""
    if m.get("key") != "rumor_pressure" or m.get("op") != "set":
        return False
    v = m.get("value")
    if not isinstance(v, dict):
        return False
    if "none" not in v:
        return False
    # Remap "none" to a sane default faction key.
    v = dict(v)
    v["xi.faction.local"] = v.get("xi.faction.local", v["none"])
    del v["none"]
    m["value"] = v
    return True


def fix_legacy_rumor_in_node(node: Dict[str, Any]) -> int:
    """Fix legacy rumor keys across all choices. Returns number of changes."""
    changed = 0
    choices = node.get("choices") or {}
    for cid in ("A", "B", "C"):
        ch = choices.get(cid) or {}
        eff = ch.get("effects") or {}
        muts = eff.get("q2_mutations") or []
        if isinstance(muts, list):
            for m in muts:
                if isinstance(m, dict) and _fix_legacy_rumor_in_mut(m):
                    changed += 1
    return changed


EVENT_CYCLE = (
    ("nemesis", "A pattern survives you. It is learning your habits."),
    ("puzzle", "The place offers a rule. The trick is noticing when it changes."),
    ("revelation", "Something becomes true here. Not foreverâ€”just enough to matter."),
)


def inject_event_beats(node: Dict[str, Any], n: int) -> bool:
    """Every ~12 nodes, add node['event'] if absent."""
    if n % 12 != 0:
        return False
    if node.get("event"):
        return False
    kind, hint = EVENT_CYCLE[(n // 12) % len(EVENT_CYCLE)]
    node["event"] = {
        "kind": kind,
        "hint": hint,
        # author can later add: title, npc_id, puzzle_id, etc.
    }
    return True


MILESTONE_FACTS = {
    10: "FACT_PASS_LISTENS_TO_COUNTING",
    25: "FACT_RIME_GROWS_IN_PULSES",
    50: "FACT_WIND_PANES_ALIGN_TO_STONE",
    75: "FACT_THE_CUT_REMEMBERS_DEBTS",
    100: "FACT_EXIT_IS_NOT_SAFETY",
}

MILESTONE_LOCKS = {
    25: "LOCK_SHORTCUT_MARKED",
    50: "LOCK_SAFE_MARKS_COST_YOU",
    75: "LOCK_WITNESS_DEBT_EXISTS",
}


def inject_milestones(node: Dict[str, Any], n: int) -> bool:
    changed = False
    if n in MILESTONE_FACTS:
        node.setdefault("facts_add", [])
        if MILESTONE_FACTS[n] not in node["facts_add"]:
            node["facts_add"].append(MILESTONE_FACTS[n])
            changed = True
    if n in MILESTONE_LOCKS:
        node.setdefault("locks_add", [])
        if MILESTONE_LOCKS[n] not in node["locks_add"]:
            node["locks_add"].append(MILESTONE_LOCKS[n])
            changed = True
    return changed


def inject_clock_ws_effects(node: Dict[str, Any], n: int) -> bool:
    """Very small node-level ws_effects to create structure.

    - Every 8 nodes: inc tension +1 (soft clock)
    - Every 20 nodes: relief beat: dec tension -2 and band_set noise_budget one step better via 'noise_budget_relief'
      (actual band step is handled by simulator render/system; here we just set a flag).
    """
    muts: List[Dict[str, Any]] = []
    if n % 8 == 0:
        muts.append({"op": "inc", "path": "/tension_index", "value": 1})
    if n % 20 == 0:
        muts.append({"op": "dec", "path": "/tension_index", "value": 2})
        muts.append({"op": "flag_add", "path": "/flags/status", "value": "RELIEF_BREATH"})

    if not muts:
        return False

    # Respect Q2 cap by only keeping first 2 mutations.
    node.setdefault("ws_effects", [])
    for m in muts[:2]:
        node["ws_effects"].append(m)
    return True


def upgrade(path_in: str, path_out: str) -> Dict[str, int]:
    rows = list(iter_jsonl(path_in))

    stats = {
        "nodes": 0,
        "legacy_rumor_fixes": 0,
        "event_beats_added": 0,
        "milestones_added": 0,
        "clock_effects_added": 0,
    }

    for node in rows:
        stats["nodes"] += 1
        nid = node.get("node_id", "")
        n = node_number(nid)
        if n is None:
            continue

        stats["legacy_rumor_fixes"] += fix_legacy_rumor_in_node(node)
        if inject_event_beats(node, n):
            stats["event_beats_added"] += 1
        if inject_milestones(node, n):
            stats["milestones_added"] += 1
        if inject_clock_ws_effects(node, n):
            stats["clock_effects_added"] += 1

    write_jsonl(path_out, rows)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="path_in", required=True)
    ap.add_argument("--out", dest="path_out", required=True)
    args = ap.parse_args()

    stats = upgrade(args.path_in, args.path_out)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
