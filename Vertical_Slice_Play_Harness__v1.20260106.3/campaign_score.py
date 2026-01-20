#!/usr/bin/env python3
"""campaign_score.py

Quick heuristic scorer for Harness scene_nodes JSONL campaigns.

Outputs a JSON report with:
- node count
- loopiness (back-edges / self-edges)
- fact/lock usage
- event beat usage
- mutation density
- inspect bait estimate (how often inspect exists vs other systems)

Run:
  python campaign_score.py --in campaigns/RUN_001.scene_nodes.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any, Dict, List, Tuple


NODE_RE = re.compile(r"^N(\d+)$")


def iter_jsonl(path: str):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def node_num(nid: str) -> int | None:
    m = NODE_RE.match(nid or "")
    return int(m.group(1)) if m else None


def score(path: str) -> Dict[str, Any]:
    nodes = list(iter_jsonl(path))
    by_id = {n.get("node_id"): n for n in nodes}

    edges: List[Tuple[str, str]] = []
    back_edges = 0
    self_edges = 0
    total_edges = 0

    facts = 0
    locks = 0
    events = 0
    ws_effect_nodes = 0
    choice_ws_muts = 0
    legacy_muts = 0

    for n in nodes:
        nid = n.get("node_id")
        nn = node_num(nid)

        if n.get("facts_add"):
            facts += len(n.get("facts_add") or [])
        if n.get("locks_add"):
            locks += len(n.get("locks_add") or [])
        if n.get("event"):
            events += 1
        if n.get("ws_effects"):
            ws_effect_nodes += 1

        choices = (n.get("choices") or {})
        for cid, ch in choices.items():
            nxt = (ch or {}).get("next")
            if not nxt:
                continue
            total_edges += 1
            edges.append((nid, nxt))
            if nxt == nid:
                self_edges += 1
            else:
                a = nn
                b = node_num(nxt)
                if a is not None and b is not None and b < a:
                    back_edges += 1

            eff = (ch or {}).get("effects") or {}
            if eff.get("ws_effects"):
                choice_ws_muts += len(eff.get("ws_effects") or [])
            if eff.get("q2_mutations"):
                legacy_muts += len(eff.get("q2_mutations") or [])

    loopiness = 0.0
    if total_edges:
        loopiness = (back_edges + self_edges) / float(total_edges)

    # crude "variety" score
    variety = 0
    variety += min(20, events * 2)
    variety += min(20, (facts + locks))
    variety += min(20, ws_effect_nodes)
    variety += min(20, int((choice_ws_muts + legacy_muts) / 10))
    variety += int(max(0, 20 - loopiness * 40))

    return {
        "path": path,
        "nodes": len(nodes),
        "edges": total_edges,
        "back_edges": back_edges,
        "self_edges": self_edges,
        "loopiness": round(loopiness, 3),
        "facts_added": facts,
        "locks_added": locks,
        "event_nodes": events,
        "ws_effect_nodes": ws_effect_nodes,
        "choice_ws_effect_count": choice_ws_muts,
        "legacy_mutation_count": legacy_muts,
        "variety_score_0_100": max(0, min(100, variety)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="path", required=True)
    args = ap.parse_args()
    print(json.dumps(score(args.path), indent=2))


if __name__ == "__main__":
    main()
