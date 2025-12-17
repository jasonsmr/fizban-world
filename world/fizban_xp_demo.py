#!/usr/bin/env python3
"""
fizban_xp_demo.py

Quick test of the XP engine:
Paladin (lvl 5) & Puck (lvl 4) vs 3 goblins + 1 wolf in a forest region.
"""

from __future__ import annotations
import json

from fizban_xp import (
    EncounterMonster,
    EncounterContext,
    compute_encounter_xp,
    social_xp_for_event,
    relationship_xp_from_trust_delta,
)


def main() -> None:
    ctx = EncounterContext(
        monsters=[
            EncounterMonster(key="GOBLIN_SCOUT", quantity=3),
            EncounterMonster(key="WOLF", quantity=1),
        ],
        party_levels={
            "Paladin": 5,
            "Puck": 4,
        },
        world_difficulty_scalar=1.0,
        region_level_hint=3.0,  # feels like a CR 3-ish fight overall
    )

    combat_result = compute_encounter_xp(ctx)

    # pretend we had a social moment:
    # Paladin helps the villagers afterwards (good_deed),
    # and their affinity with a local NPC goes from 0.0 -> 0.25
    paladin_social_xp = social_xp_for_event(
        level=5,
        kind="good_deed",
        intensity=1.0,
        world_scalar=1.0,
    )
    paladin_rel_xp = relationship_xp_from_trust_delta(
        level=5,
        affinity_before=0.0,
        affinity_after=0.25,
        betrayal_delta=0.0,
        world_scalar=1.0,
    )

    out = {
        "encounter": {
            "total_base_xp": combat_result.total_base_xp,
            "total_effective_xp": combat_result.total_effective_xp,
            "per_agent": [vars(p) for p in combat_result.per_agent],
        },
        "paladin_social_xp_example": {
            "good_deed_xp": paladin_social_xp,
            "relationship_xp": paladin_rel_xp,
            "total_social_xp": paladin_social_xp + paladin_rel_xp,
        },
    }

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

