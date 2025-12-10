#!/usr/bin/env python3
"""
fizban_behavior_demo.py

Demo wiring traits + favor into the behavior engine without depending on
other world modules. Uses the same favor / trait intuition as the
earlier Fizban demos.
"""

from __future__ import annotations

import json

from fizban_behavior import (
    BehaviorInputs,
    behavior_profile_to_dict,
    compute_behavior_profile,
)


def build_paladin_inputs() -> BehaviorInputs:
    # Mirrors your trait / favor intuition from fizban_traits_demo + fizban_gods.
    traits = [
        "class_paladin",
        "divine_knight",
        "hero",
        "lawful_good",
        "king_chosen",
        "titania_favored",
        "oberon_favored",
        "queen_favored",
        "lovers_favored",
        "bottom_favored",
    ]
    favor = {
        "Titania": 0.5739339828220179,
        "Oberon": 0.5939339828220179,
        "Bottom": 0.4128291754873716,
        "King": 0.7800000000000001,
        "Queen": 0.5,
        "Lovers": 0.65,
    }
    return BehaviorInputs(
        name="Paladin",
        alignment_label="Lawful Good",
        alignment_coords=(1.0, 1.0),
        traits=traits,
        favor=favor,
        trust_affinity=0.1,  # cautiously positive
        weird_level=0.1,
    )


def build_puck_inputs() -> BehaviorInputs:
    traits = [
        "class_rogue",
        "trickster",
        "trickster_heart",
        "chaotic_neutral",
        "embraces_chaos",
        "bottom_chosen",
        "titania_favored",
        "oberon_favored",
        "king_favored",
        "queen_favored",
        "lovers_favored",
    ]
    favor = {
        "Titania": 0.515,
        "Oberon": 0.43786796564403574,
        "Bottom": 0.8,
        "King": 0.4128291754873716,
        "Queen": 0.5439339828220179,
        "Lovers": 0.65,
    }
    return BehaviorInputs(
        name="Puck",
        alignment_label="Chaotic Neutral",
        alignment_coords=(-1.0, 0.0),
        traits=traits,
        favor=favor,
        trust_affinity=0.0,  # keeps options open
        weird_level=0.3,
    )


def main() -> None:
    paladin_profile = compute_behavior_profile(build_paladin_inputs())
    puck_profile = compute_behavior_profile(build_puck_inputs())

    out = {
        "paladin_behavior": behavior_profile_to_dict(paladin_profile),
        "puck_behavior": behavior_profile_to_dict(puck_profile),
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

