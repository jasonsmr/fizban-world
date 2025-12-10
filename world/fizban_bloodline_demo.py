#!/usr/bin/env python3
"""
fizban_bloodline_demo.py

Show several bloodlines at different levels / favor states.
"""

from __future__ import annotations

import json

from fizban_bloodline import (
    evaluate_bloodline_progress,
    make_bloodline_angelic_scion,
    make_bloodline_demonic_infernal,
    make_bloodline_forest_heir_druidic,
)


def main() -> None:
    angel = make_bloodline_angelic_scion()
    demon = make_bloodline_demonic_infernal()
    forest = make_bloodline_forest_heir_druidic()

    paladin = {
        "name": "Paladin",
        "level": 22,
        "weird_level": 0.15,
        "favor": {"King": 0.55, "Titania": 0.52},
        "traits": ["hero", "lawful_good", "devout", "class_paladin"],
    }

    succubus = {
        "name": "Veliss",
        "level": 24,
        "weird_level": 0.2,
        "favor": {"Bottom": 0.55},
        "traits": ["ambitious", "chaotic_neutral", "trickster"],
    }

    druid = {
        "name": "Arianel",
        "level": 16,
        "weird_level": 0.13,
        "favor": {"Titania": 0.5, "Queen": 0.35},
        "traits": ["forest_child", "class_druid"],
    }

    out = {
        "paladin_angelic": evaluate_bloodline_progress(
            angel, paladin["level"], paladin["weird_level"], paladin["favor"], paladin["traits"]
        ),
        "succubus_demonic": evaluate_bloodline_progress(
            demon, succubus["level"], succubus["weird_level"], succubus["favor"], succubus["traits"]
        ),
        "druid_forest": evaluate_bloodline_progress(
            forest, druid["level"], druid["weird_level"], druid["favor"], druid["traits"]
        ),
    }

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

