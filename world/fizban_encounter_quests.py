#!/usr/bin/env python3
"""
fizban_encounter_quests.py

Lightweight encounter-quest generator that ties together:
- difficulty_profile.json (regions + world scalar)
- monsters/core_bestary.json (bestiary archetypes)
- a very simple XP hint per agent

This is deliberately conservative and robust:
- It filters by region_id via archetype["region_tags"]
- It uses CR bands derived from difficulty_profile, but will
  gracefully relax filters instead of raising if nothing matches.
"""

from __future__ import annotations

import json
import math
import os
import random
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional


HERE = os.path.dirname(__file__)
BESTIARY_PATH = os.path.join(HERE, "monsters", "core_bestary.json")
DIFFICULTY_PATH = os.path.join(HERE, "difficulty_profile.json")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Archetype:
    id: str
    name: str
    cr: float
    base_xp: int
    role: str
    type: str
    tags: List[str]
    alignment_hint: str
    region_tags: List[str]
    behavior_hint: Dict[str, Any]

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Archetype":
        return Archetype(
            id=d["id"],
            name=d["name"],
            cr=float(d["cr"]),
            base_xp=int(d["base_xp"]),
            role=d.get("role", "standard"),
            type=d.get("type", "unknown"),
            tags=list(d.get("tags", [])),
            alignment_hint=d.get("alignment_hint", "unknown"),
            region_tags=list(d.get("region_tags", [])),
            behavior_hint=dict(d.get("behavior_hint", {})),
        )


@dataclass
class EncounterMonster:
    archetype_id: str
    name: str
    count: int
    cr: float
    role: str
    tags: List[str]
    xp_each: int
    xp_total: int


@dataclass
class EncounterQuest:
    id: str
    title: str
    patron: Optional[str]
    agent: str
    region_id: str
    region_label: str
    difficulty: str
    danger: str
    tags: List[str]
    summary: str
    monsters: List[EncounterMonster]
    xp_total: int
    xp_per_agent_hint: Dict[str, int]


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------

def load_bestiary(path: str = BESTIARY_PATH) -> Dict[str, Archetype]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {k: Archetype.from_dict(v) for k, v in raw.items()}


def load_difficulty(path: str = DIFFICULTY_PATH) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Core encounter construction
# ---------------------------------------------------------------------------

def _cr_band_for_region(region_cfg: Dict[str, Any], difficulty: str) -> (float, float):
    """
    Very simple CR band:
    - base_cr +/- cr_variance
    - difficulty nudges the upper bound a bit
    """
    base = float(region_cfg.get("base_cr", 1.0))
    var = float(region_cfg.get("cr_variance", 1.0))

    min_cr = max(0.125, base - var)
    max_cr = base + var

    if difficulty == "easy":
        max_cr = max(base, base + var * 0.5)
    elif difficulty == "hard":
        max_cr = base + var * 1.5

    return (min_cr, max_cr)


def _filter_archetypes_for_region(
    archetypes: Dict[str, Archetype],
    region_id: str,
    region_cfg: Dict[str, Any],
    difficulty: str,
) -> List[Archetype]:
    """
    Filter archetypes by region + CR band.
    If the band is too strict and yields no results, we relax step by step.
    """
    min_cr, max_cr = _cr_band_for_region(region_cfg, difficulty)

    # First: region + CR band
    region_matches = [
        a for a in archetypes.values()
        if region_id in a.region_tags
    ]
    band_matches = [
        a for a in region_matches
        if min_cr <= a.cr <= max_cr
    ]

    if band_matches:
        return band_matches

    # Second: region only
    if region_matches:
        return region_matches

    # Third: CR band only (if truly no region matches, which shouldn't happen)
    band_only = [
        a for a in archetypes.values()
        if min_cr <= a.cr <= max_cr
    ]
    if band_only:
        return band_only

    # Last resort: anything at all, sorted by CR ascending
    fallback = sorted(archetypes.values(), key=lambda a: a.cr)
    return fallback


def _choose_monster_counts(
    archetype: Archetype,
    party_size: int,
    difficulty: str,
) -> int:
    """
    Very rough rule of thumb for a count:
    - minions: more copies
    - elite: fewer
    - medium difficulty ~1x-1.5x party size
    """
    party_size = max(1, party_size)
    base = party_size

    role = archetype.role.lower()
    if role == "minion":
        base *= 2
    elif role in ("elite", "controller", "leader"):
        base = max(1, math.ceil(party_size / 2))

    if difficulty == "easy":
        base = max(1, math.floor(base * 0.75))
    elif difficulty == "hard":
        base = max(1, math.ceil(base * 1.25))

    return base


def build_encounter_quest(
    *,
    region_id: str,
    agent_name: str,
    agent_level: int,
    patron: Optional[str] = None,
    difficulty: str = "medium",
    party_size: int = 2,
    world_time_hours: float = 0.0,
) -> EncounterQuest:
    """
    Construct a single encounter quest for an agent in a region.

    This uses:
    - difficulty_profile.json for region config + world scalar
    - monsters/core_bestary.json for archetypes
    """

    difficulty_data = load_difficulty(DIFFICULTY_PATH)
    bestiary = load_bestiary(BESTIARY_PATH)

    global_cfg = difficulty_data.get("global", {})
    regions_cfg = difficulty_data.get("regions", {})

    region_cfg = regions_cfg.get(region_id, {})
    region_label = region_cfg.get("label", region_id.title().replace("_", " "))

    world_scalar = float(global_cfg.get("world_difficulty_scalar", 1.0))
    auto_level = bool(global_cfg.get("world_auto_leveling", True))
    world_level_per_hours = float(global_cfg.get("world_level_per_hours", 0.02))

    effective_level = float(agent_level)
    if auto_level:
        effective_level += world_time_hours * world_level_per_hours

    # Filter archetypes
    candidates = _filter_archetypes_for_region(
        bestiary,
        region_id=region_id,
        region_cfg=region_cfg,
        difficulty=difficulty,
    )

    # Choose 1-2 archetypes to represent this encounter
    num_types = 1
    if difficulty == "hard" and len(candidates) >= 2:
        num_types = 2

    chosen = random.sample(candidates, k=num_types)

    monsters: List[EncounterMonster] = []
    xp_total = 0

    for archetype in chosen:
        count = _choose_monster_counts(archetype, party_size=party_size, difficulty=difficulty)
        xp_each = archetype.base_xp
        xp_sum = xp_each * count
        xp_total += xp_sum

        monsters.append(
            EncounterMonster(
                archetype_id=archetype.id,
                name=archetype.name,
                count=count,
                cr=archetype.cr,
                role=archetype.role,
                tags=archetype.tags,
                xp_each=xp_each,
                xp_total=xp_sum,
            )
        )

    # Apply world scalar to total XP
    xp_total = int(round(xp_total * world_scalar))

    # Simple hint: even split across party
    xp_per_agent = int(round(xp_total / max(1, party_size)))
    xp_per_agent_hint = {agent_name: xp_per_agent}

    qid = f"ENC_{region_id}_{difficulty}_{agent_name}".upper()

    # Rough danger label
    if difficulty == "easy":
        danger = "easy"
    elif difficulty == "hard":
        danger = "deadly"
    else:
        danger = "medium"

    # Tags blend region, monsters, and patron if present
    tags: List[str] = [region_id.lower(), difficulty]
    for m in monsters:
        tags.extend(m.tags)
    if patron:
        tags.append(patron.lower())

    # Short flavor summary
    monster_names = ", ".join(sorted({m.name for m in monsters}))
    summary = (
        f"An encounter near the {region_label.lower()} where {monster_names} "
        f"threaten the area. Designed for {agent_name} around level {int(effective_level)}."
    )

    return EncounterQuest(
        id=qid,
        title=f"Skirmish in the {region_label}",
        patron=patron,
        agent=agent_name,
        region_id=region_id,
        region_label=region_label,
        difficulty=difficulty,
        danger=danger,
        tags=sorted(list(set(tags))),
        summary=summary,
        monsters=monsters,
        xp_total=xp_total,
        xp_per_agent_hint=xp_per_agent_hint,
    )


# ---------------------------------------------------------------------------
# Demo payload
# ---------------------------------------------------------------------------

def demo_payload() -> Dict[str, Any]:
    """
    Build two demo quests:
    - Paladin in STARTING_FOREST
    - Puck in KINGDOM_BORDER
    """
    random.seed(42)

    forest_quest = build_encounter_quest(
        region_id="STARTING_FOREST",
        agent_name="Paladin",
        agent_level=5,
        patron="King",
        difficulty="medium",
        party_size=2,
        world_time_hours=3.0,
    )

    border_quest = build_encounter_quest(
        region_id="KINGDOM_BORDER",
        agent_name="Puck",
        agent_level=6,
        patron="Bottom",
        difficulty="hard",
        party_size=2,
        world_time_hours=12.0,
    )

    return {
        "forest_quest": {
            **{k: v for k, v in asdict(forest_quest).items() if k != "monsters"},
            "monsters": [asdict(m) for m in forest_quest.monsters],
        },
        "border_quest": {
            **{k: v for k, v in asdict(border_quest).items() if k != "monsters"},
            "monsters": [asdict(m) for m in border_quest.monsters],
        },
    }


if __name__ == "__main__":
    print(json.dumps(demo_payload(), indent=2))

