#!/usr/bin/env python3
"""
fizban_world_enrich_demo.py

Demo: build a tiny Paladin + Puck world and enrich it with:
- bloodlines
- forest heirloom item (for a druidic friend)
"""

from __future__ import annotations

import json

from fizban_world_enrich import enrich_world


def build_demo_world() -> dict:
    paladin = {
        "name": "Paladin",
        "alignment": {
            "law_chaos": "LAWFUL",
            "good_evil": "GOOD",
            "label": "Lawful Good",
            "default_strategy": "Copykitten",
            "coords": [1, 1],
        },
        "class": {
            "dnd_class": "paladin",
            "level": 22,
            "job_tags": ["tank", "frontline", "divine"],
        },
        "tags": [
            "hero",
            "lawful_good",
            "class_paladin",
            "king_chosen",
            "devout",
        ],
        "fate": {
            "grace": 0.6,
            "bounce_back": 0.5,
            "mental_strain": 0.1,
            "weird_mode": False,
        },
        "favor": {
            "Titania": 0.52,
            "Oberon": 0.45,
            "Bottom": 0.2,
            "King": 0.55,
            "Queen": 0.4,
            "Lovers": 0.35,
        },
        "trust": {},
        "level": 22,
    }

    puck = {
        "name": "Puck",
        "alignment": {
            "law_chaos": "CHAOTIC",
            "good_evil": "NEUTRAL",
            "label": "Chaotic Neutral",
            "default_strategy": "Random",
            "coords": [-1, 0],
        },
        "class": {
            "dnd_class": "rogue",
            "level": 24,
            "job_tags": ["thief", "trickster"],
        },
        "tags": [
            "trickster",
            "chaotic_neutral",
            "class_rogue",
            "embraces_chaos",
            "ambitious",
        ],
        "fate": {
            "grace": 0.55,
            "bounce_back": 0.6,
            "mental_strain": 0.08,
            "weird_mode": True,
        },
        "favor": {
            "Titania": 0.5,
            "Oberon": 0.43,
            "Bottom": 0.6,
            "King": 0.3,
            "Queen": 0.35,
            "Lovers": 0.5,
        },
        "trust": {},
        "level": 24,
    }

    # A druid friend to show forest + item combo
    druid = {
        "name": "Arianel",
        "alignment": {
            "law_chaos": "NEUTRAL",
            "good_evil": "GOOD",
            "label": "Neutral Good",
            "default_strategy": "Copykitten",
            "coords": [0, 1],
        },
        "class": {
            "dnd_class": "druid",
            "level": 16,
            "job_tags": ["healer", "caster"],
        },
        "tags": ["forest_child", "class_druid"],
        "fate": {
            "grace": 0.55,
            "bounce_back": 0.5,
            "mental_strain": 0.15,
            "weird_mode": False,
        },
        "favor": {
            "Titania": 0.5,
            "Queen": 0.35,
        },
        "stats": {
            "near_death_events": 2,
            "forest_rites_completed": 1,
        },
        "trust": {},
        "level": 16,
    }

    return {
        "world_final": {
            "agents": {
                "Paladin": paladin,
                "Puck": puck,
                "Arianel": druid,
            }
        }
    }


def main() -> None:
    base_world = build_demo_world()
    enriched = enrich_world(base_world)
    print(json.dumps(enriched, indent=2))


if __name__ == "__main__":
    main()

