#!/usr/bin/env python3
"""
fizban_sentient_item_demo.py

Show:
- creating the forest ancestor heirloom
- bonding it to an elf druid-esque character
- seeing abilities and fate tweaks
"""

from __future__ import annotations

import json

from fizban_sentient_item import (
    apply_item_to_fate,
    granted_abilities_for_item,
    make_forest_ancestor_heirloom,
    tick_item_bond,
)


def main() -> None:
    item = make_forest_ancestor_heirloom()

    # Example character: forest elf druid with hidden bloodline
    agent = {
        "name": "Arianel",
        "level": 7,
        "class": "druid",
        "traits": ["forest_child", "bloodline_forest_heir_druidic"],
        "fate": {
            "grace": 0.55,
            "bounce_back": 0.5,
            "mental_strain": 0.15,
            "weird_mode": False,
        },
        "stats": {
            "near_death_events": 2,
            "forest_rites_completed": 1,
        },
    }

    # Bond over a couple dramatic sessions.
    item = tick_item_bond(
        item,
        agent_name=agent["name"],
        events={
            "quest_completed": 3,
            "trauma": 2,
            "betrayed_item_values": False,
        },
    )

    abilities = granted_abilities_for_item(item, agent_level=agent["level"])
    fate_after = apply_item_to_fate(item, agent["fate"])

    out = {
        "agent": agent,
        "item": item.to_dict(),
        "abilities_granted": abilities,
        "fate_after": fate_after,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

