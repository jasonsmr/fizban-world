#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_dialogue.py

Translate agent state (trust, emotion, alignment, relationship, bounce-back)
into which dialogue archetypes are available from A -> B.
"""


from typing import Dict, Any

from fizban_agent import AgentState


def _get_relationship_view(a: AgentState, b: AgentState) -> Dict[str, Any]:
    rel = a.relationships.get(b.id)
    if rel is None:
        return {
            "tier": "none",
            "affinity": 0.0,
            "romantic": False,
        }
    return {
        "tier": rel.tier,
        "affinity": rel.affinity,
        "romantic": rel.romantic,
    }


def compute_dialogue_slots(agent: AgentState, other: AgentState) -> Dict[str, bool]:
    """
    Decide which dialogue options are unlocked from `agent` toward `other`.

    Uses:
      - trust in other.id
      - emotional valence & strain
      - resentment & cooldown
      - relationship tier/affinity/romantic
    """
    other_id = other.id
    rel = agent.relationships.get(other_id)

    trust = agent.get_trust(other_id)
    val = agent.emotion.valence
    strain = agent.emotion.strain
    cooldown = agent.bounce_back.cooldown
    resentment = agent.bounce_back.resentment

    tier = rel.tier if rel is not None else "stranger"
    affinity = rel.affinity if rel is not None else 0.0
    romantic = rel.romantic if rel is not None else False

    # --- Basic availability gates ---

    # If someone is in hard cooldown or extreme strain, everything except
    # maybe "intimidate" is off the table.
    if cooldown >= 3 or strain > 0.8:
        return {
            "small_talk": False,
            "trade": False,
            "ask_favor": False,
            "confide_secret": False,
            "romantic_flirt": False,
            "intimidate": True,
            "apologize": False,
            "betrayal_offer": False,
        }

    # --- Small talk & trade: fairly easy to unlock ---
    small_talk = True  # almost always available unless we are in extreme hate
    if trust < -0.8 and val < -0.5:
        small_talk = False

    trade = trust > -0.2 and resentment < 0.9

    # --- Ask favor & confide secret ---

    # Asking favors: need moderate trust and not too much resentment.
    ask_favor = trust > 0.5 and resentment < 0.4

    # Confiding secrets: higher bar; either strong trust + low resentment,
    # or a more intimate relationship tier.
    confide_secret = False
    if trust > 0.75 and resentment < 0.25:
        confide_secret = True
    elif tier in ("ally", "permanent_follower", "love_interest") and trust > 0.5 and resentment < 0.35:
        confide_secret = True

    # --- Romance ---
    romantic_flirt = False
    if romantic or tier == "love_interest":
        if trust > 0.0 and val > 0.0 and resentment < 0.4:
            romantic_flirt = True

    # --- Intimidate ---
    intimidate = False
    if trust < 0.0 or strain > 0.6:
        intimidate = True

    # --- Apologize ---
    # Available when there is *some* hurt (resentment), but still enough
    # trust and positive emotion that reconciliation is plausible.
    apologize = False
    if resentment > 0.05 and resentment < 0.6 and trust > 0.3 and val > -0.2:
        apologize = True

    # --- Betrayal offer ---
    # "Join me in something shady" – more likely when trust is low/negative
    # but resentment is also low (they don't hate you, just don't trust you).
    betrayal_offer = False
    if trust < 0.0 and resentment < 0.3 and val >= 0.0:
        betrayal_offer = True

    return {
        "small_talk": small_talk,
        "trade": trade,
        "ask_favor": ask_favor,
        "confide_secret": confide_secret,
        "romantic_flirt": romantic_flirt,
        "intimidate": intimidate,
        "apologize": apologize,
        "betrayal_offer": betrayal_offer,
    }

