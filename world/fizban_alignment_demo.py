#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_alignment_demo.py

Small demo:
- Create a Lawful Good paladin and a Chaotic Neutral rogue Puck
- Run a series of Prisoner's Dilemma rounds with trust updates
- Apply a betrayal event and fate ticks
- Save snapshots and series logs under world/examples/
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict

from fizban_alignment import (
    Alignment,
    LawChaos,
    GoodEvil,
    AgentState,
    TrustLink,
    update_trust_after_round,
    tick_fate_after_event,
    destiny_roll,
    save_agents,
    save_series_jsonl,
)


ROOT = Path(__file__).resolve().parent
EXAMPLES_DIR = ROOT / "examples"


def make_paladin() -> AgentState:
    return AgentState(
        name="Paladin",
        alignment=Alignment(LawChaos.LAWFUL, GoodEvil.GOOD),
        dnd_class="paladin",
        tags=["hero", "lawful_good", "tank"],
    )


def make_puck() -> AgentState:
    return AgentState(
        name="Puck",
        alignment=Alignment(LawChaos.CHAOTIC, GoodEvil.NEUTRAL),
        dnd_class="rogue",
        tags=["trickster", "chaotic_neutral", "thief"],
    )


def run_series(rounds_before_betrayal: int = 10, betrayal_rounds: int = 2) -> None:
    pal = make_paladin()
    puck = make_puck()

    pal.ensure_link("Puck")
    puck.ensure_link("Paladin")

    series_records: List[Dict] = []

    # Phase 1: mutual cooperation
    for n in range(1, rounds_before_betrayal + 1):
        link_p = pal.ensure_link("Puck")
        link_u = puck.ensure_link("Paladin")

        update_trust_after_round(link_p, "CC", learning_rate=0.15)
        update_trust_after_round(link_u, "CC", learning_rate=0.15)

        tick_fate_after_event(pal, "heroic_deed", intensity=0.5)
        tick_fate_after_event(puck, "love_moment", intensity=0.3)

        series_records.append(
            {
                "round": n,
                "phase": "cooperation",
                "pal_trust": link_p.to_dict(),
                "puck_trust": link_u.to_dict(),
                "pal_fate": pal.fate.to_dict(),
                "puck_fate": puck.fate.to_dict(),
            }
        )

    # Phase 2: Puck betrays Paladin (Puck defects, Paladin cooperates)
    for k in range(1, betrayal_rounds + 1):
        round_idx = rounds_before_betrayal + k
        link_p = pal.ensure_link("Puck")
        link_u = puck.ensure_link("Paladin")

        # From Paladin's perspective: CD (he cooperated, Puck defected)
        update_trust_after_round(link_p, "CD", learning_rate=0.3)
        # From Puck's perspective: DC
        update_trust_after_round(link_u, "DC", learning_rate=0.1)

        tick_fate_after_event(pal, "betrayal", intensity=1.0)
        tick_fate_after_event(puck, "heroic_deed", intensity=0.2)  # survived the drama

        series_records.append(
            {
                "round": round_idx,
                "phase": "betrayal",
                "pal_trust": link_p.to_dict(),
                "puck_trust": link_u.to_dict(),
                "pal_fate": pal.fate.to_dict(),
                "puck_fate": puck.fate.to_dict(),
            }
        )

    # One destiny roll each post-betrayal
    pal_destiny = destiny_roll(pal, base_dc=12)
    puck_destiny = destiny_roll(puck, base_dc=12)

    # Save final agents snapshot
    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    save_agents(EXAMPLES_DIR / "paladin_puck_alignment_demo.json", [pal, puck])

    # Save series as JSONL
    save_series_jsonl(EXAMPLES_DIR / "paladin_puck_alignment_series.jsonl", series_records)

    # Also print short summary to stdout
    print("=== Final Snapshot ===")
    print(json.dumps({"paladin": pal.to_dict(), "puck": puck.to_dict()}, indent=2))
    print("\n=== Destiny Rolls ===")
    print(json.dumps({"paladin": pal_destiny, "puck": puck_destiny}, indent=2))


def main() -> int:
    run_series(rounds_before_betrayal=10, betrayal_rounds=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

