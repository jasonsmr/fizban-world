#!/usr/bin/env python3
"""
fizban_xp.py

XP engine for Fizban-World:
- Combat XP from monsters (CR-based, SRD-style).
- Social / quest XP hooks.
- Diminishing returns for low-challenge content.
- World difficulty scalar so the whole world can "keep up".
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
import json
import math
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MONSTER_FILE = BASE_DIR / "monsters" / "core_bestary.json"

# SRD-like CR -> XP table (subset; extend if you like).
# Values taken from the standard 5e XP/CR table. :contentReference[oaicite:6]{index=6}
XP_BY_CR: Dict[float, int] = {
    0.0: 10,
    0.125: 25,
    0.25: 50,
    0.5: 100,
    1.0: 200,
    2.0: 450,
    3.0: 700,
    4.0: 1100,
    5.0: 1800
    # ... you can extend this up to CR 30 if desired
}

def load_monsters() -> Dict[str, dict]:
    with MONSTER_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def base_xp_for_monster(mon: dict) -> int:
    """Return raw XP for one monster from its CR or explicit xp_cr_base."""
    if "xp_cr_base" in mon:
        return int(mon["xp_cr_base"])
    cr = float(mon["cr"])
    if cr in XP_BY_CR:
        return XP_BY_CR[cr]
    # simple fallback if you add weird CRs before updating the table
    return int(100 * max(cr, 0.125))


def multi_monster_modifier(n: int) -> float:
    """
    Roughly mimic 5e DMG multi-monster scaling without copying it exactly.
    1   -> 1.0
    2   -> 1.3
    3-4 -> 1.5
    5-6 -> 1.7
    7+  -> 2.0
    """
    if n <= 1:
        return 1.0
    if n == 2:
        return 1.3
    if 3 <= n <= 4:
        return 1.5
    if 5 <= n <= 6:
        return 1.7
    return 2.0


def level_gap_factor(agent_level: int, challenge_level: float) -> float:
    """
    Diminishing (or increasing) returns based on how hard the content is
    compared to the agent's level.

    gap = challenge_level - agent_level
    - gap <= -4  -> trivial, 0.1x
    - gap = -3   -> 0.25x
    - gap = -2   -> 0.5x
    - gap = -1   -> 0.75x
    - -0..+2     -> 1.0x
    - gap = +3   -> 1.25x
    - gap >= +4  -> 1.5x
    """
    gap = challenge_level - agent_level
    if gap <= -4:
        return 0.1
    if gap == -3:
        return 0.25
    if gap == -2:
        return 0.5
    if gap == -1:
        return 0.75
    if -0.999 <= gap <= 2:
        return 1.0
    if gap == 3:
        return 1.25
    return 1.5


@dataclass
class EncounterMonster:
    key: str
    quantity: int = 1


@dataclass
class EncounterContext:
    monsters: List[EncounterMonster]
    party_levels: Dict[str, int]  # agent_name -> level
    world_difficulty_scalar: float = 1.0  # 0.5 story mode, 1.0 normal, 1.5 hard
    region_level_hint: Optional[float] = None  # average CR / level for the area


@dataclass
class XPResultPerAgent:
    agent: str
    level: int
    xp_gained: int
    source: str
    details: Dict[str, float]


@dataclass
class EncounterXPResult:
    total_base_xp: int
    total_effective_xp: int
    per_agent: List[XPResultPerAgent]


def compute_encounter_xp(ctx: EncounterContext) -> EncounterXPResult:
    monsters_data = load_monsters()

    # 1) Raw XP + approximate "challenge level" for the encounter
    total_base_xp = 0
    total_cr_weighted = 0.0
    total_count = 0

    for m in ctx.monsters:
        mon = monsters_data[m.key]
        mxp = base_xp_for_monster(mon)
        total_base_xp += mxp * m.quantity
        total_cr_weighted += float(mon["cr"]) * m.quantity
        total_count += m.quantity

    avg_cr = total_cr_weighted / max(total_count, 1)
    multi_mod = multi_monster_modifier(total_count)
    effective_xp = int(total_base_xp * multi_mod * ctx.world_difficulty_scalar)

    # 2) Split across party with diminishing returns per agent
    per_agent: List[XPResultPerAgent] = []
    base_share = effective_xp / max(len(ctx.party_levels), 1)

    challenge_level = ctx.region_level_hint or avg_cr

    for agent, level in ctx.party_levels.items():
        gap_factor = level_gap_factor(level, challenge_level)
        agent_xp = int(round(base_share * gap_factor))
        per_agent.append(
            XPResultPerAgent(
                agent=agent,
                level=level,
                xp_gained=agent_xp,
                source="combat",
                details={
                    "base_share": base_share,
                    "challenge_level": challenge_level,
                    "gap_factor": gap_factor,
                    "world_scalar": ctx.world_difficulty_scalar,
                    "multi_monster_modifier": multi_mod,
                },
            )
        )

    return EncounterXPResult(
        total_base_xp=total_base_xp,
        total_effective_xp=effective_xp,
        per_agent=per_agent,
    )


# --- Social / quest XP hooks -----------------------------------------------

def social_xp_for_event(
    level: int,
    kind: str,
    intensity: float = 1.0,
    world_scalar: float = 1.0,
) -> int:
    """
    Generic social XP:
    kind in { 'good_deed', 'evil_deed', 'relationship_milestone',
              'betrayal', 'forgiveness', 'big_reveal' }

    intensity ~ 0.0-2.0 (rough scale).
    """
    base_by_kind = {
        "good_deed": 15,
        "evil_deed": 15,
        "relationship_milestone": 50,
        "betrayal": 40,
        "forgiveness": 40,
        "big_reveal": 75,
    }
    base = base_by_kind.get(kind, 10)
    # mild level scaling: early levels feel bigger, later levels need more
    level_factor = 1.0 + 0.02 * max(level - 1, 0)
    xp = int(round(base * intensity * level_factor * world_scalar))
    return xp


def relationship_xp_from_trust_delta(
    level: int,
    affinity_before: float,
    affinity_after: float,
    betrayal_delta: float = 0.0,
    world_scalar: float = 1.0,
) -> int:
    """
    Tiny helper that can be called from the trust engine:
    - reward large positive affinity changes
    - also reward meaningful *negative* shifts as story fuel
    """
    delta = affinity_after - affinity_before
    magnitude = abs(delta)
    base = 0

    if magnitude < 0.05:
        return 0  # too small to care

    # big swings in either direction generate story XP
    if magnitude < 0.2:
        base = 10
    elif magnitude < 0.5:
        base = 25
    else:
        base = 50

    # betrayal bump if desired
    if betrayal_delta > 0:
        base += int(20 * betrayal_delta)

    level_factor = 1.0 + 0.01 * max(level - 1, 0)
    return int(round(base * level_factor * world_scalar))

