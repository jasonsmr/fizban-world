#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_betrayal_offers.py

Skeleton for god-vs-god betrayal quests.

Design:
- Only available at high levels (e.g. >= 100).
- Requires strong favor with one god and non-trivial favor with another.
- Produces offers of the form:

  {
    "id": "BETRAY_OBERON_FOR_BOTTOM",
    "requester": "Bottom",
    "target": "Oberon",
    "prereqs": {...},
    "reward": {...},
    "curses": [...],
    "story_hook": "Burn Oberon's trade shrine..."
  }

Execution (actually applying rewards/curses) is left to the world engine.
"""

from __future__ import annotations

from typing import Dict, List, Any

from fizban_gods import compute_favor_for_agent


BetrayalOffer = Dict[str, Any]


def _candidate_pairs() -> List[tuple]:
    """
    Hard-coded interesting god rivalry pairs for now.
    """
    return [
        ("Bottom", "Oberon"),
        ("Oberon", "Bottom"),
        ("Titania", "Oberon"),
        ("Titania", "Bottom"),
        ("Lovers", "Titania"),
        ("Lovers", "Bottom"),
    ]


def get_betrayal_offers(agent: Dict, *, min_level: int = 100) -> List[BetrayalOffer]:
    """
    Given an agent with favor computed, return high-risk, high-reward betrayal quests.

    Rules (for now):
    - agent["class"]["level"] >= min_level
    - requester favor >= 0.6
    - target favor >= 0.3
    """
    level = int(agent.get("class", {}).get("level", 0))
    if level < min_level:
        return []

    favor = compute_favor_for_agent(agent)
    agent_name = agent.get("name", "Unknown")

    offers: List[BetrayalOffer] = []

    for requester, target in _candidate_pairs():
        f_req = float(favor.get(requester, 0.0))
        f_tgt = float(favor.get(target, 0.0))

        if f_req >= 0.6 and f_tgt >= 0.3:
            offer_id = f"BETRAY_{target.upper()}_FOR_{requester.upper()}"
            story_hook = _build_story_hook(agent_name, requester, target)
            reward, curses = _build_reward_and_curses(requester, target)

            offers.append(
                {
                    "id": offer_id,
                    "agent": agent_name,
                    "requester": requester,
                    "target": target,
                    "prereqs": {
                        "min_level": min_level,
                        "min_favor_requester": 0.6,
                        "min_favor_target": 0.3,
                        "favor_snapshot": favor,
                    },
                    "reward": reward,
                    "curses": curses,
                    "story_hook": story_hook,
                }
            )

    return offers


def _build_story_hook(agent_name: str, requester: str, target: str) -> str:
    """
    Narrative seed for the quest.
    """
    if requester == "Bottom" and target == "Oberon":
        return (
            f"Bottom pulls {agent_name} aside with a wicked grin. "
            "“Oberon has grown too proud of his tidy ledgers. "
            "Burn one of his trade shrines to the ground, and I will "
            "show you tricks the forest forgot.”"
        )

    if requester == "Oberon" and target == "Bottom":
        return (
            f"Oberon sends a sealed contract to {agent_name}. "
            "\"Bottom's chaos bleeds into my markets. Break one of his "
            "masquerade circles and I'll stamp you with a permanent mark of trade.\""
        )

    return (
        f"{requester} whispers to {agent_name}, offering you a chance to wound "
        f"{target}'s pride in exchange for a dangerous boon."
    )


def _build_reward_and_curses(requester: str, target: str) -> tuple:
    """
    Very rough placeholder: maps requester/target into:
    - reward.effects (traits, abilities, etc.)
    - curse specs (for fizban_curse.add_curse)
    """
    reward: Dict[str, Any] = {
        "traits_add": [],
        "abilities_add": [],
        "favor_delta": {},
        "notes": "",
    }
    curses: List[Dict[str, Any]] = []

    # Simple archetypes
    if requester == "Bottom":
        reward["traits_add"].append("bottom_favored")
        reward["abilities_add"].append("tricksters_boon")
        reward["favor_delta"]["Bottom"] = +0.2
        reward["notes"] = "Bottom grants you a strange, high-variance boon."

    if requester == "Oberon":
        reward["traits_add"].append("oberon_favored")
        reward["abilities_add"].append("merchant_champion")
        reward["favor_delta"]["Oberon"] = +0.2
        reward["notes"] = "Oberon stamps you as a golden child of trade."

    # Punishment: target locks your new boons (freeze, not delete) for a while
    curses.append(
        {
            "id": f"CURSE_{target.upper()}_RESENTS_YOU",
            "source": target,
            "type": "PATRON_LOCK",
            "target_patron": target,
            "duration_rounds": 100,
            "remaining_rounds": 100,
            "severity": 0.9,
        }
    )

    return reward, curses

