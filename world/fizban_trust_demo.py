#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_trust_demo.py

Demo: Paladin vs Puck trust evolution.

- Creates two TrustState objects:
    paladin_view_of_puck
    puck_view_of_paladin

- Runs a short scripted outcome sequence and prints the evolution
  as JSON so we can later feed this into Fizban's world or memory logs.
"""

from __future__ import annotations

import json
from typing import List, Dict

from fizban_alignment_math import alignment_to_axes
from fizban_trust_math import (
    TrustState,
    init_trust_state,
    update_trust_state,
)


def main() -> int:
    paladin_align = "Lawful Good"
    puck_align = "Chaotic Neutral"

    paladin_alignment = alignment_to_axes(paladin_align)
    puck_alignment = alignment_to_axes(puck_align)

    paladin_trust = init_trust_state(
        my_alignment=paladin_alignment.label,
        other_alignment=puck_alignment.label,
        base_gossip=0.0,
        base_awe=0.2,       # Paladin is mildly impressed by Puck's heroics
        base_boredom=0.0,
    )

    puck_trust = init_trust_state(
        my_alignment=puck_alignment.label,
        other_alignment=paladin_alignment.label,
        base_gossip=0.0,
        base_awe=0.4,       # Puck finds Paladin kind of awe-inspiring
        base_boredom=0.0,
    )

    # Scripted outcomes from Paladin's POV:
    #   round 1: CC (both cooperate)
    #   round 2: CC
    #   round 3: CC
    #   round 4: CD (Paladin cooperates, Puck defects -> betrayal)
    #   round 5: CC (Paladin forgives and they cooperate again)
    #
    # For Puck's POV, the outcomes are mirrored:
    #   if Paladin's POV is "CD", then Puck's POV is "DC".
    rounds_paladin = ["CC", "CC", "CC", "CD", "CC"]
    rounds_puck = []
    for out in rounds_paladin:
        if out == "CC":
            rounds_puck.append("CC")
        elif out == "CD":
            rounds_puck.append("DC")
        elif out == "DC":
            rounds_puck.append("CD")
        elif out == "DD":
            rounds_puck.append("DD")

    history: List[Dict[str, object]] = []

    for i, (pal_out, puck_out) in enumerate(zip(rounds_paladin, rounds_puck), start=1):
        # Basic emotional tweaks per round (toy values)
        awe_boost_pal = 0.05 if pal_out == "CC" else 0.0
        awe_boost_puck = 0.05 if puck_out == "CC" else 0.02
        boredom_boost_pal = 0.02 if pal_out == "DD" else 0.0
        boredom_boost_puck = 0.01 if puck_out == "DD" else 0.0

        new_pal_trust, deltas_pal = update_trust_state(
            paladin_trust,
            pal_out,
            awe_boost=awe_boost_pal,
            boredom_boost=boredom_boost_pal,
            gossip_delta=0.0,
            bounce=0.1,
        )
        new_puck_trust, deltas_puck = update_trust_state(
            puck_trust,
            puck_out,
            awe_boost=awe_boost_puck,
            boredom_boost=boredom_boost_puck,
            gossip_delta=0.0,
            bounce=0.1,
        )

        history.append(
            {
                "round": i,
                "paladin_outcome": pal_out,
                "puck_outcome": puck_out,
                "paladin_trust": new_pal_trust.to_dict(),
                "puck_trust": new_puck_trust.to_dict(),
                "paladin_deltas": deltas_pal,
                "puck_deltas": deltas_puck,
            }
        )

        paladin_trust = new_pal_trust
        puck_trust = new_puck_trust

    snapshot = {
        "paladin_alignment": paladin_alignment.__dict__,
        "puck_alignment": puck_alignment.__dict__,
        "history": history,
    }

    print("=== Paladin vs Puck Trust Demo ===")
    print(json.dumps(snapshot, indent=2))
    print("\nNote: You can save this JSON to world/examples/ and replay it later.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

