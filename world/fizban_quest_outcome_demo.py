#!/usr/bin/env python3
"""
fizban_quest_outcome_demo.py - Show how quest outcomes modify agents.

This uses:
- fizban_quests.generate_quests_for_agent
- fizban_quest_outcome.apply_quest_outcome

and prints before/after snapshots + summaries.
"""

from __future__ import annotations

import json

from fizban_quests import generate_quests_for_agent
from fizban_quest_outcome import apply_quest_outcome


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
        "abilities": [],
        "favor": {
            "Titania": 0.58,
            "Oberon": 0.52,
            "Bottom": 0.35,
            "King": 0.62,
            "Queen": 0.42,
            "Lovers": 0.55,
        },
        "curses": [],
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
        "abilities": [],
        "favor": {
            "Titania": 0.51,
            "Oberon": 0.38,
            "Bottom": 0.82,
            "King": 0.40,
            "Queen": 0.50,
            "Lovers": 0.67,
        },
        "curses": [],
    }

    return paladin, puck


def pick_quest(offers, quest_id_prefix: str | None = None):
    """Pick first quest, or first whose id starts with quest_id_prefix."""
    if not offers:
        return None
    if quest_id_prefix is None:
        return offers[0]
    for q in offers:
        if str(q["id"]).startswith(quest_id_prefix):
            return q
    return None


def main():
    paladin, puck = build_demo_agents()

    paladin_offers = [
        q.__dict__ for q in generate_quests_for_agent(
            agent_name=paladin["name"],
            level=paladin["level"],
            traits=paladin["traits"],
            favor=paladin["favor"],
        )
    ]
    puck_offers = [
        q.__dict__ for q in generate_quests_for_agent(
            agent_name=puck["name"],
            level=puck["level"],
            traits=puck["traits"],
            favor=puck["favor"],
        )
    ]

    # 1) Paladin: King border quest (success)
    king_quest = pick_quest(paladin_offers, quest_id_prefix="Q_KING_DEFEND_BORDER")
    paladin_after_king, paladin_king_summary = (
        apply_quest_outcome(paladin, king_quest, "success")
        if king_quest is not None
        else (paladin, {"error": "no_king_quest"})
    )

    # 2) Puck: Bottom masquerade quest (success)
    bottom_quest = pick_quest(puck_offers, quest_id_prefix="Q_BOTTOM_MASQUERADE")
    puck_after_bottom, puck_bottom_summary = (
        apply_quest_outcome(puck, bottom_quest, "success")
        if bottom_quest is not None
        else (puck, {"error": "no_bottom_quest"})
    )

    # 3) Paladin: Lovers betrayal quest, if present, to show betrayal curse
    lovers_quest = pick_quest(paladin_offers, quest_id_prefix="Q_LOVERS_STOLEN_VOW")
    paladin_after_lovers, paladin_lovers_summary = (
        apply_quest_outcome(paladin_after_king, lovers_quest, "success")
        if lovers_quest is not None
        else (paladin_after_king, {"info": "no_lovers_betrayal_quest_in_offers"})
    )

    out = {
        "before": {
            "Paladin": paladin,
            "Puck": puck,
        },
        "after": {
            "Paladin": paladin_after_lovers,
            "Puck": puck_after_bottom,
        },
        "summaries": {
            "paladin_king": paladin_king_summary,
            "paladin_lovers": paladin_lovers_summary,
            "puck_bottom": puck_bottom_summary,
        },
        "debug": {
            "paladin_offers_ids": [q["id"] for q in paladin_offers],
            "puck_offers_ids": [q["id"] for q in puck_offers],
        },
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

