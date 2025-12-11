#!/usr/bin/env python3
"""
fizban_god_reactions_demo.py

Build the same demo world as fizban_world_enrich_demo,
enrich it, then ask the gods what they think.
"""

from __future__ import annotations

import json

from fizban_world_enrich import enrich_world
from fizban_world_enrich_demo import build_demo_world
from fizban_god_reactions import compute_god_reactions


def main() -> None:
    base_world = build_demo_world()
    enriched = enrich_world(base_world)

    # Example event feed: in a real game, this comes from your engine per tick/session.
    events = [
        {
            "type": "LEVEL_UP",
            "agent": "Paladin",
            "node_id": "TITANIA_GRACE_SPARK",
            "source": "TITANIA_CORE_TREE",
        },
        {
            "type": "BLOODLINE_TIER_UNLOCKED",
            "agent": "Paladin",
            "bloodline": "angelic",
            "tier_id": "angelic_latent",
        },
        {
            "type": "ITEM_BOND_TICK",
            "agent": "Arianel",
            "item_id": "ITEM_FOREST_ANCESTOR_HEIRLOOM",
        },
    ]

    reactions = compute_god_reactions(enriched, events=events)

    # Print a compact summary
    print(
        json.dumps(
            {
                patron: {
                    "headline": data["headline"],
                    "top_lines": data["top_lines"],
                }
                for patron, data in reactions.items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

