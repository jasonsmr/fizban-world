#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_paladin_tree_demo.py

Show how the Paladin's Oath tree looks and which nodes
are currently legal, using existing helpers.
"""

from __future__ import annotations

from pathlib import Path
import json

from fizban_level_menu import _load_agent_from_v2, load_all_trees
from fizban_level_tree import eligible_nodes_for_tree


def _demo() -> int:
    base_dir = Path(__file__).resolve().parent
    examples_dir = base_dir / "examples"

    paladin_path = examples_dir / "agent_paladin_v2.json"
    paladin = _load_agent_from_v2(paladin_path)

    trees = load_all_trees(base_dir)
    paladin_tree = trees.get("PALADIN_OATH_CORE_TREE")

    if paladin_tree is None:
        print(json.dumps({"error": "PALADIN_OATH_CORE_TREE not found"}, indent=2))
        return 1

    eligible_entries = [
        {
            "tree_id": paladin_tree.tree_id,
            "node_id": node.node_id,
            "name": node.name,
            "tier": getattr(node, "tier", None),
            "tags": getattr(node, "tags", []),
        }
        for node in eligible_nodes_for_tree(paladin, paladin_tree)
    ]

    out = {
        "agent_level": paladin.get("class", {}).get("level"),
        "tree_id": paladin_tree.tree_id,
        "tree_label": paladin_tree.label,
        "eligible_nodes": eligible_entries,
    }

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_demo())

