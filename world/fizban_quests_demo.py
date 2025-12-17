#!/usr/bin/env python3
"""
fizban_quests_demo.py - Show example quest offers for Paladin & Puck.

For now, this demo is self-contained and *does not* pull from fizban_world_enrich.
Later, you can swap in real world state:

- level <- world_final["agents"][name]["class"]["level"]
- traits <- traits engine
- favor <- gods favor engine
"""

from __future__ import annotations

import json

from fizban_quests import generate_quests_for_agent


def build_demo_agents():
    paladin = {
        "name": "Paladin",
        "level": 15,
        "traits": [
            "hero",
            "devout",
            "lawful_good",
            "titania_favored",
            "king_chosen",
        ],
        "favor": {
            "Titania": 0.58,
            "Oberon": 0.52,
            "Bottom": 0.35,
            "King": 0.62,
            "Queen": 0.42,
            "Lovers": 0.55,
        },
    }

    puck = {
        "name": "Puck",
        "level": 11,
        "traits": [
            "trickster",
            "chaotic_neutral",
            "bottom_favored",
            "lovers_favored",
            "embraces_chaos",
        ],
        "favor": {
            "Titania": 0.51,
            "Oberon": 0.38,
            "Bottom": 0.82,
            "King": 0.40,
            "Queen": 0.50,
            "Lovers": 0.67,
        },
    }

    return paladin, puck


def main():
    paladin, puck = build_demo_agents()

    paladin_offers = generate_quests_for_agent(
        agent_name=paladin["name"],
        level=paladin["level"],
        traits=paladin["traits"],
        favor=paladin["favor"],
    )

    puck_offers = generate_quests_for_agent(
        agent_name=puck["name"],
        level=puck["level"],
        traits=puck["traits"],
        favor=puck["favor"],
    )

    out = {
        "paladin_offers": [q.__dict__ for q in paladin_offers],
        "puck_offers": [q.__dict__ for q in puck_offers],
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

