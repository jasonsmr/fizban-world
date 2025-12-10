#!/usr/bin/env python3
"""
fizban_sentient_item.py

Sentient items that:
- have their own alignment, desires, fears, voice
- are bound to a bloodline
- can grant abilities/traits and tweak fate/behavior over time
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple


@dataclass
class SentientVoice:
    """
    One of possibly several internal voices.
    Example: ancestor spirit, demon fragment, angel shard.
    """

    id: str
    name: str
    tone_tags: List[str]  # "kind", "harsh", "cryptic", "seductive"
    desires: List[str]  # "protect_forest", "seek_power", "free_bloodline"
    fears: List[str]  # "being_forgotten", "losing_host"
    alignment_label: str
    alignment_coords: Tuple[float, float]  # (-1..1, -1..1)


@dataclass
class SentientItem:
    id: str
    name: str
    rank: str  # "minor", "greater", "artifact"
    bound_to: Optional[str]  # agent name, if currently bound
    origin_bloodline: Optional[str]  # bloodline id like "forest_heir_druidic"
    alignment_label: str
    alignment_coords: Tuple[float, float]
    voices: List[SentientVoice]
    personality_tags: List[str]  # "snarky", "mentor", "bloodthirsty"
    bond_depth: float  # 0..1 how bonded to current wielder
    awaken_triggers: Dict[str, float]
    # earliest tier of abilities the item can grant
    base_abilities: List[str]
    # progressive unlocks by bond_depth/level
    tier_abilities: Dict[str, List[str]]
    # fate tweaks the item makes over time
    fate_modifiers: Dict[str, float]  # grace_delta, strain_delta, weird_bias etc

    def to_dict(self) -> Dict:
        return asdict(self)


def make_forest_ancestor_heirloom() -> SentientItem:
    """
    Example: forest druid elf with an ancestral spirit trapped in a staff/amulet.
    Inspired by your story about the hidden bloodline + sentient item.
    """
    main_voice = SentientVoice(
        id="ancestor_elyndor",
        name="Elyndor of the Green Bough",
        tone_tags=["patient", "protective", "stern", "cryptic"],
        desires=[
            "protect_forest",
            "guide_heir",
            "atone_for_ancient_failure",
        ],
        fears=["being_forgotten", "forest_burns", "heir_corrupted"],
        alignment_label="Neutral Good",
        alignment_coords=(0.0, 1.0),
    )

    return SentientItem(
        id="ITEM_FOREST_ANCESTOR_HEIRLOOM",
        name="Heartroot Diadem",
        rank="greater",
        bound_to=None,
        origin_bloodline="forest_heir_druidic",
        alignment_label="Neutral Good",
        alignment_coords=(0.0, 1.0),
        voices=[main_voice],
        personality_tags=["mentor", "forest", "memory_hoarder"],
        bond_depth=0.0,
        awaken_triggers={
            "min_level": 5,
            "near_death_events": 1,
            "forest_rites_completed": 1,
        },
        base_abilities=[
            "sense_forest_disturbance",
            "whisper_of_old_paths",
        ],
        tier_abilities={
            "tier1": ["rapid_regeneration_minor", "poison_resistance"],
            "tier2": ["regeneration_major", "barkskin_aura"],
            "tier3": ["forest_step", "commune_with_ancestors"],
        },
        fate_modifiers={
            "grace_delta": 0.05,          # more likely to survive dumb choices
            "strain_delta": -0.02,        # mental strain eases a bit
            "weird_bias": 0.1,            # more weird forest visions
        },
    )


# --- interaction helpers --------------------------------------------------


def can_item_awaken(item: SentientItem, agent_level: int, stats: Dict) -> bool:
    """
    Check if awaken conditions are met.
    stats can include:
      - "near_death_events"
      - "forest_rites_completed"
    """
    t = item.awaken_triggers
    nde = float(stats.get("near_death_events", 0))
    rites = float(stats.get("forest_rites_completed", 0))

    if agent_level < t.get("min_level", 0):
        return False
    if nde < t.get("near_death_events", 0):
        return False
    if rites < t.get("forest_rites_completed", 0):
        return False
    return True


def tick_item_bond(item: SentientItem, agent_name: str, events: Dict) -> SentientItem:
    """
    Advance bond depth based on recent events:
      - "quest_completed": float
      - "trauma": float
      - "betrayed_item_values": bool
    """
    bond = item.bond_depth
    quest = float(events.get("quest_completed", 0.0))
    trauma = float(events.get("trauma", 0.0))
    betrayed = bool(events.get("betrayed_item_values", False))

    # More quests completed in line with the item's desires deepen bond.
    bond += 0.05 * quest
    # Near-death/trauma moments shared deepen bond too.
    bond += 0.03 * trauma
    # Betraying the item's core desires erodes bond.
    if betrayed:
        bond -= 0.2

    bond = max(0.0, min(1.0, bond))

    return SentientItem(
        **{
            **asdict(item),
            "bound_to": agent_name,
            "bond_depth": bond,
        }
    )


def granted_abilities_for_item(item: SentientItem, agent_level: int) -> List[str]:
    """
    Compute which abilities the item is currently willing to grant.
    Very rough rule-of-thumb: each 0.33 bond_depth and +5 levels unlocks a tier.
    """
    abilities: List[str] = list(item.base_abilities)

    depth = item.bond_depth
    tiers_unlocked = 0
    if depth >= 0.33 and agent_level >= 5:
        tiers_unlocked += 1
    if depth >= 0.66 and agent_level >= 10:
        tiers_unlocked += 1
    if depth >= 0.9 and agent_level >= 15:
        tiers_unlocked += 1

    if tiers_unlocked >= 1:
        abilities.extend(item.tier_abilities.get("tier1", []))
    if tiers_unlocked >= 2:
        abilities.extend(item.tier_abilities.get("tier2", []))
    if tiers_unlocked >= 3:
        abilities.extend(item.tier_abilities.get("tier3", []))

    return sorted(set(abilities))


def apply_item_to_fate(
    item: SentientItem,
    fate: Dict[str, float],
) -> Dict[str, float]:
    """
    Apply the item's fate modifiers to a simple fate dict:
      { "grace": float, "bounce_back": float, "mental_strain": float, "weird_mode": bool }
    """
    out = dict(fate)
    out["grace"] = out.get("grace", 0.5) + item.fate_modifiers.get("grace_delta", 0.0)
    out["mental_strain"] = out.get("mental_strain", 0.1) + item.fate_modifiers.get(
        "strain_delta", 0.0
    )

    weird_bias = item.fate_modifiers.get("weird_bias", 0.0)
    if weird_bias > 0:
        out["weird_mode"] = bool(out.get("weird_mode", False) or weird_bias > 0.05)
    return out


if __name__ == "__main__":
    # Tiny smoke
    import json

    item = make_forest_ancestor_heirloom()
    item = tick_item_bond(
        item,
        agent_name="Arianel",
        events={"quest_completed": 2, "trauma": 1, "betrayed_item_values": False},
    )
    fate = {"grace": 0.6, "bounce_back": 0.5, "mental_strain": 0.2, "weird_mode": False}
    print(
        json.dumps(
            {
                "item": item.to_dict(),
                "abilities": granted_abilities_for_item(item, agent_level=8),
                "fate_after": apply_item_to_fate(item, fate),
            },
            indent=2,
        )
    )

