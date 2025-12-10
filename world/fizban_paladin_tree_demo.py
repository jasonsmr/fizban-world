#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_paladin_tree_demo.py

Show how the Paladin's Oath tree looks and which nodes
are currently legal, using only JSON + favor logic.

This is intentionally self-contained so it doesn't depend
on internal helpers from fizban_level_tree.
"""

from __future__ import annotations

from pathlib import Path
import json
from typing import Dict, Any, List

from fizban_level_menu import _load_agent_from_v2
from fizban_gods import compute_favor_for_agent


def _load_paladin_tree(base_dir: Path) -> Dict[str, Any]:
    tree_path = base_dir / "trees" / "paladin_oath_core.json"
    with tree_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _is_node_eligible(
    agent: Dict[str, Any],
    favor: Dict[str, float],
    unlocked_nodes: List[str],
    node: Dict[str, Any],
) -> bool:
    requires = node.get("requires", {})

    # Level gate
    min_level = int(requires.get("min_level", 0))
    level = int(agent.get("class", {}).get("level", 0))
    if level < min_level:
        return False

    # Favor gates
    min_favor = requires.get("min_favor", {})
    for patron, threshold in min_favor.items():
        if float(favor.get(patron, 0.0)) < float(threshold):
            return False

    # Prereq nodes (by node_id)
    prereq_nodes = requires.get("prereq_nodes", [])
    if prereq_nodes:
        unlocked_set = set(unlocked_nodes)
        for nid in prereq_nodes:
            if nid not in unlocked_set:
                return False

    # Alignment hint is *advisory*; we don't enforce it here
    return True


def _demo() -> int:
    base_dir = Path(__file__).resolve().parent
    examples_dir = base_dir / "examples"

    paladin_path = examples_dir / "agent_paladin_v2.json"
    paladin = _load_agent_from_v2(paladin_path)

    tree = _load_paladin_tree(base_dir)
    favor = compute_favor_for_agent(paladin)

    unlocked_nodes: List[str] = (
        paladin.get("unlocks", {}).get("level_nodes", []) or []
    )

    eligible_nodes: List[Dict[str, Any]] = []
    for node in tree.get("nodes", []):
        if _is_node_eligible(paladin, favor, unlocked_nodes, node):
            eligible_nodes.append(
                {
                    "tree_id": tree.get("tree_id"),
                    "node_id": node.get("node_id"),
                    "name": node.get("name"),
                    "tier": node.get("tier"),
                    "tags": node.get("tags", []),
                }
            )

    out = {
        "agent_name": paladin.get("name", "Paladin"),
        "agent_level": paladin.get("class", {}).get("level"),
        "favor": favor,
        "tree_id": tree.get("tree_id"),
        "tree_label": tree.get("label"),
        "eligible_nodes": eligible_nodes,
    }

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_demo())

