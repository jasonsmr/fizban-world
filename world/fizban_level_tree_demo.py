#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_level_tree_demo.py

Demo:
- Load agent_paladin_v2.json and agent_puck_v2.json
- Compute gods' favor
- Load Titania's core tree
- Show eligible Titania boons for each
- Apply first eligible boon to Paladin
"""

from __future__ import annotations

from pathlib import Path
import json

from fizban_gods import compute_favor_for_world
from fizban_level_tree import (
    load_level_tree,
    eligible_nodes_for_agent,
    apply_levelup_node,
)


def _load_agent_from_v2(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    name = data.get("name", path.stem)
    alignment = data.get("alignment", {})
    cls = data.get("class", {})
    tags = data.get("tags", [])
    fate_baseline = data.get(
        "fate_baseline",
        {"grace": 0.5, "bounce_back": 0.5, "mental_strain": 0.1, "weird_mode": False},
    )
    level = cls.get("level", data.get("level", 1))

    return {
        "name": name,
        "alignment": alignment,
        "class": cls,
        "tags": tags,
        "fate": {
            "grace": float(fate_baseline.get("grace", 0.5)),
            "bounce_back": float(fate_baseline.get("bounce_back", 0.5)),
            "mental_strain": float(fate_baseline.get("mental_strain", 0.1)),
            "weird_mode": bool(fate_baseline.get("weird_mode", False)),
        },
        "favor": {},
        "unlocks": {"level_nodes": []},
        "level": int(level),
    }


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    examples_dir = base_dir / "examples"
    trees_dir = base_dir / "trees"

    paladin_path = examples_dir / "agent_paladin_v2.json"
    puck_path = examples_dir / "agent_puck_v2.json"

    paladin = _load_agent_from_v2(paladin_path)
    puck = _load_agent_from_v2(puck_path)

    world = {"agents": {"Paladin": paladin, "Puck": puck}}

    # 1) Compute favor for all gods
    world = compute_favor_for_world(world)

    # 2) Load Titania's tree
    titania_tree_path = trees_dir / "titania_core.json"
    titania_tree = load_level_tree(titania_tree_path)

    agents = world["agents"]

    # 3) Show eligible Titania nodes for each agent
    snapshot = {"eligible": {}, "before": agents}

    for name, agent in agents.items():
        elig = eligible_nodes_for_agent(agent, titania_tree)
        snapshot["eligible"][name] = [n.id for n in elig]

    print("=== Before Level-Up (favor + eligible Titania nodes) ===")
    print(json.dumps(snapshot, indent=2))

    # 4) Apply first eligible node to Paladin, if any
    pal_elig = eligible_nodes_for_agent(agents["Paladin"], titania_tree)
    if pal_elig:
        chosen = pal_elig[0]
        apply_levelup_node(world, "Paladin", chosen)
        applied_id = chosen.id
    else:
        applied_id = None

    result = {
        "applied_node_to_paladin": applied_id,
        "world_after": world,
    }

    print("\n=== After Applying One Titania Node to Paladin ===")
    print(json.dumps(result, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

