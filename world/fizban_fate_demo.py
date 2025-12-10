#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_fate_demo.py

Demo: alignment + trust + Titania's Grace (fate) all together.

- Paladin (Lawful Good) vs Puck (Chaotic Neutral)
- Re-uses the trust engine to update per-pair trust
- Integrates trust deltas into FateState for each agent
- Shows final fate snapshots and destiny rolls
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
from fizban_fate import (
    FateState,
    init_fate_state,
    apply_trust_deltas_to_fate,
    roll_destiny,
)


def run_demo() -> Dict[str, object]:
    paladin_align_label = "Lawful Good"
    puck_align_label = "Chaotic Neutral"

    paladin_alignment = alignment_to_axes(paladin_align_label)
    puck_alignment = alignment_to_axes(puck_align_label)

    # Initial trust states (from alignment)
    paladin_trust = init_trust_state(
        my_alignment=paladin_alignment.label,
        other_alignment=puck_alignment.label,
        base_gossip=0.0,
        base_awe=0.2,
        base_boredom=0.0,
    )
    puck_trust = init_trust_state(
        my_alignment=puck_alignment.label,
        other_alignment=paladin_alignment.label,
        base_gossip=0.0,
        base_awe=0.4,
        base_boredom=0.0,
    )

    # Initial fate states (Titania's Grace)
    paladin_fate = init_fate_state(paladin_alignment.label)
    puck_fate = init_fate_state(puck_alignment.label)

    # Same script as before: CC, CC, CC, CD, CC (from Paladin POV)
    rounds_paladin = ["CC", "CC", "CC", "CD", "CC"]
    rounds_puck: List[str] = []
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
        # Awe / boredom tweaks
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

        # Integrate trust deltas into fate (Titania's Grace)
        paladin_fate = apply_trust_deltas_to_fate(
            paladin_fate,
            deltas_pal,
            awe=new_pal_trust.awe,
            boredom=new_pal_trust.boredom,
        )
        puck_fate = apply_trust_deltas_to_fate(
            puck_fate,
            deltas_puck,
            awe=new_puck_trust.awe,
            boredom=new_puck_trust.boredom,
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
                "paladin_fate": paladin_fate.to_dict(),
                "puck_fate": puck_fate.to_dict(),
            }
        )

        paladin_trust = new_pal_trust
        puck_trust = new_puck_trust

    # Final destiny rolls (D&D-style)
    paladin_roll = roll_destiny(paladin_fate, paladin_alignment.label, dc=12)
    puck_roll = roll_destiny(puck_fate, puck_alignment.label, dc=12)

    return {
        "paladin_alignment": paladin_alignment.__dict__,
        "puck_alignment": puck_alignment.__dict__,
        "history": history,
        "destiny_rolls": {
            "paladin": paladin_roll,
            "puck": puck_roll,
        },
    }


def main() -> int:
    snapshot = run_demo()
    print("=== Fate Demo: Paladin vs Puck ===")
    print(json.dumps(snapshot, indent=2))
    print(
        "\nNote: history[].paladin_fate / puck_fate show Titania's Grace evolving.\n"
        "Destiny rolls use grace/strain + weird_mode to bias the d20 outcome.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

