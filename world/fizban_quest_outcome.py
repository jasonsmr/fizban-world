#!/usr/bin/env python3
"""
fizban_quest_outcome.py - Apply quest outcomes to an agent.

Self-contained: does not import other Fizban modules.

Inputs:
- agent_state: {
    "name": str,
    "level": int,
    "traits": [str],
    "abilities": [str],
    "favor": { patron: float },
    "curses": [ {...} ]  # optional
  }

- quest: a dict in the shape of QuestOffer from fizban_quests:
  {
    "id": str,
    "title": str,
    "patron": str,
    "target_patron": Optional[str],
    "agent": str,
    "danger": "low"|"medium"|"high",
    "tags": [...],
    "summary": str,
    "reward": {
      "favor_delta": {patron: float},
      "grant_traits": [str],
      "grant_abilities": [str],
      "notes": str
    },
    "requirements": {...}
  }

- result: "success" | "failure" | "partial"

Outputs:
- (updated_agent_state, outcome_summary_dict)
"""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, List, Tuple, Any


def _apply_favor_delta(
    favor: Dict[str, float],
    delta: Dict[str, float],
    scale: float = 1.0,
) -> Dict[str, float]:
    """Apply a scaled favor delta, clamped to [0, 1]."""
    new_favor = dict(favor)
    for patron, dv in delta.items():
        v = new_favor.get(patron, 0.0)
        v += dv * scale
        if v < 0.0:
            v = 0.0
        if v > 1.0:
            v = 1.0
        new_favor[patron] = v
    return new_favor


def _merge_unique(base: List[str], extra: List[str]) -> List[str]:
    """Append entries from extra that are not yet in base."""
    s = set(base)
    out = list(base)
    for x in extra:
        if x not in s:
            out.append(x)
            s.add(x)
    return out


def _maybe_generate_betrayal_curse(
    *,
    agent_name: str,
    quest: Dict[str, Any],
    reward_favor_delta: Dict[str, float],
) -> Dict[str, Any] | None:
    """
    If quest implies god-vs-god betrayal (negative favor vs target_patron),
    produce a generic PATRON_LOCK curse stub.
    """
    target_patron = quest.get("target_patron")
    if not target_patron:
        return None

    neg = reward_favor_delta.get(target_patron, 0.0)
    if neg >= 0.0:
        return None

    severity = min(1.0, abs(neg) * 2.0)
    duration_rounds = int(100 * severity) or 10

    curse_id = f"CURSE_{target_patron.upper()}_RESENTS_{agent_name.upper()}"
    return {
        "id": curse_id,
        "source": target_patron,
        "type": "PATRON_LOCK",
        "target_patron": target_patron,
        "duration_rounds": duration_rounds,
        "remaining_rounds": duration_rounds,
        "severity": severity,
        "notes": f"{target_patron} resents {agent_name} for the quest {quest.get('id')}.",
    }


def apply_quest_outcome(
    agent_state: Dict[str, Any],
    quest: Dict[str, Any],
    result: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Apply the quest outcome to agent_state.

    result:
      - "success": full rewards + possible betrayal curse
      - "partial": half favor, full traits/abilities, no betrayal curse
      - "failure": small negative favor from the patron, and a 'quest_failed_*' trait
    """
    if result not in {"success", "partial", "failure"}:
        raise ValueError(f"Invalid result: {result}")

    agent = deepcopy(agent_state)
    name = agent.get("name", "Unknown")
    favor = dict(agent.get("favor", {}))
    traits = list(agent.get("traits", []))
    abilities = list(agent.get("abilities", []))
    curses = list(agent.get("curses", []))

    patron = quest.get("patron")
    reward = quest.get("reward", {})
    favor_delta = reward.get("favor_delta", {}) or {}
    grant_traits = reward.get("grant_traits", []) or []
    grant_abilities = reward.get("grant_abilities", []) or []

    applied_favor_delta: Dict[str, float] = {}

    if result == "success":
        # Full favor delta + all traits/abilities.
        new_favor = _apply_favor_delta(favor, favor_delta, scale=1.0)
        # Record what actually changed, relative to original favor
        for k, v_after in new_favor.items():
            v_before = favor.get(k, 0.0)
            if abs(v_after - v_before) > 1e-9:
                applied_favor_delta[k] = v_after - v_before
        favor = new_favor

        traits = _merge_unique(traits, grant_traits)
        abilities = _merge_unique(abilities, grant_abilities)

        # Maybe add betrayal curse if this quest pits patrons against each other
        curse = _maybe_generate_betrayal_curse(
            agent_name=name,
            quest=quest,
            reward_favor_delta=favor_delta,
        )
        if curse is not None:
            curses.append(curse)

    elif result == "partial":
        # Half favor, full traits/abilities, no betrayal curse.
        new_favor = _apply_favor_delta(favor, favor_delta, scale=0.5)
        for k, v_after in new_favor.items():
            v_before = favor.get(k, 0.0)
            if abs(v_after - v_before) > 1e-9:
                applied_favor_delta[k] = v_after - v_before
        favor = new_favor

        traits = _merge_unique(traits, grant_traits)
        abilities = _merge_unique(abilities, grant_abilities)

    else:  # "failure"
        # Patron is disappointed: small negative favor from patron only.
        # Also add a 'quest_failed_*' trait as a scar/hook.
        penalty = -0.1
        if patron:
            new_favor = _apply_favor_delta(favor, {patron: penalty}, scale=1.0)
            v_before = favor.get(patron, 0.0)
            v_after = new_favor.get(patron, 0.0)
            if abs(v_after - v_before) > 1e-9:
                applied_favor_delta[patron] = v_after - v_before
            favor = new_favor

        fail_trait = f"quest_failed_{quest.get('id', 'unknown').lower()}"
        traits = _merge_unique(traits, [fail_trait])

    # Write back updated fields
    agent["favor"] = favor
    agent["traits"] = traits
    agent["abilities"] = abilities
    agent["curses"] = curses

    outcome_summary = {
        "agent": name,
        "quest_id": quest.get("id"),
        "quest_title": quest.get("title"),
        "result": result,
        "applied_favor_delta": applied_favor_delta,
        "gained_traits": [t for t in traits if t not in agent_state.get("traits", [])],
        "gained_abilities": [a for a in abilities if a not in agent_state.get("abilities", [])],
        "new_curses": [c for c in curses if c not in agent_state.get("curses", [])],
    }
    return agent, outcome_summary


__all__ = ["apply_quest_outcome"]

