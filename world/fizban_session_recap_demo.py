#!/usr/bin/env python3
"""
fizban_session_recap_demo.py

- Build base demo world
- Enrich it -> world_before
- Clone and tweak -> world_after (simulate some progress)
- Run compute_session_recap and print the result
"""

from __future__ import annotations

import copy
import json
from typing import Any, Dict

from fizban_world_enrich_demo import build_demo_world
from fizban_world_enrich import enrich_world
from fizban_session_recap import compute_session_recap


World = Dict[str, Any]


def tweak_world_for_demo(world: World) -> World:
    """
    Simulate one session of progress.

    - Paladin gains a level and a bit more favor with King/Titania.
    - Paladin's fate grace bumps slightly.
    - Arianel's bond with Heartroot Diadem deepens.
    - Puck amuses Bottom a bit more, annoys Oberon a bit more.
    """
    w = copy.deepcopy(world)
    agents = w.get("world_final", {}).get("agents", {})

    pal = agents.get("Paladin")
    puck = agents.get("Puck")
    arianel = agents.get("Arianel")

    # Paladin: level up, small fate shift, favor changes
    if pal:
        # Level bump
        if isinstance(pal.get("level"), (int, float)):
            pal["level"] = int(pal["level"]) + 1
        elif "class" in pal and isinstance(pal["class"].get("level"), (int, float)):
            pal["class"]["level"] = int(pal["class"]["level"]) + 1

        # Fate
        fate = pal.setdefault("fate", {})
        fate["grace"] = float(fate.get("grace", 0.6)) + 0.05
        fate["mental_strain"] = float(fate.get("mental_strain", 0.1)) + 0.01

        # Favor
        favor = pal.setdefault("favor", {})
        favor["King"] = float(favor.get("King", 0.4)) + 0.07
        favor["Titania"] = float(favor.get("Titania", 0.5)) + 0.05

    # Puck: grows in Bottom's favor, annoys Oberon
    if puck:
        favor = puck.setdefault("favor", {})
        favor["Bottom"] = float(favor.get("Bottom", 0.8)) + 0.05
        favor["Oberon"] = float(favor.get("Oberon", 0.45)) - 0.06

    # Arianel: deepen sentient bond
    if arianel:
        items = arianel.get("sentient_items") or {}
        diadem = items.get("ITEM_FOREST_ANCESTOR_HEIRLOOM")
        if diadem:
            item_obj = diadem.get("item", {})
            item_obj["bond_depth"] = float(item_obj.get("bond_depth", 0.11)) + 0.12

    return w


def main() -> None:
    base_world = build_demo_world()

    # Enrich both worlds, then tweak "after"
    before_enriched: World = enrich_world(base_world)
    after_enriched: World = tweak_world_for_demo(enrich_world(base_world))

    events = [
        {
            "type": "LEVEL_UP",
            "agent": "Paladin",
            "node_id": "TITANIA_GRACE_SPARK",
            "source": "TITANIA_CORE_TREE",
        },
        {
            "type": "BOND_DEEPENED",
            "agent": "Arianel",
            "item_id": "ITEM_FOREST_ANCESTOR_HEIRLOOM",
        },
        {
            "type": "FAVOR_SHIFT",
            "agent": "Puck",
            "patron_gain": "Bottom",
            "patron_loss": "Oberon",
        },
    ]

    recap = compute_session_recap(before_enriched, after_enriched, events=events)

    # Pretty print
    print(json.dumps(recap, indent=2))


if __name__ == "__main__":
    main()

