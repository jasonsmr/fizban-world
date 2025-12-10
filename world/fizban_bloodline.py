#!/usr/bin/env python3
"""
fizban_bloodline.py

Bloodlines (angelic, demonic, druidic, psionic) that:
- define tiers: latent, stirring, awakened, transcendent
- plug into traits/favor/fate
- can unlock sentient items and special abilities
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


@dataclass
class BloodlineTier:
    id: str
    label: str
    min_level: int
    min_weird: float
    min_favor: Dict[str, float]
    required_traits_any: List[str]
    grants_traits: List[str]
    grants_abilities: List[str]
    notes: str = ""


@dataclass
class Bloodline:
    id: str
    label: str
    core_alignment_hint: str
    patron_hint: Optional[str]
    tiers: List[BloodlineTier]

    def to_dict(self) -> Dict:
        return asdict(self)


def _tier(
    id: str,
    label: str,
    min_level: int,
    min_weird: float,
    min_favor: Dict[str, float],
    required_traits_any: List[str],
    grants_traits: List[str],
    grants_abilities: List[str],
    notes: str = "",
) -> BloodlineTier:
    return BloodlineTier(
        id=id,
        label=label,
        min_level=min_level,
        min_weird=min_weird,
        min_favor=min_favor,
        required_traits_any=required_traits_any,
        grants_traits=grants_traits,
        grants_abilities=grants_abilities,
        notes=notes,
    )


# --- example bloodlines ---------------------------------------------------


def make_bloodline_angelic_scion() -> Bloodline:
    return Bloodline(
        id="bloodline_angelic_scion",
        label="Angelic Scion",
        core_alignment_hint="Lawful/Good leaning",
        patron_hint="Titania/King or other high-order patrons",
        tiers=[
            _tier(
                id="angelic_latent",
                label="Latent Radiance",
                min_level=1,
                min_weird=0.0,
                min_favor={"King": 0.3},
                required_traits_any=["devout", "hero", "lawful_good"],
                grants_traits=["bloodline_angelic_latent"],
                grants_abilities=["radiant_sense", "gentle_light"],
                notes="Subtle glow, resistant to fear and despair.",
            ),
            _tier(
                id="angelic_stirring",
                label="Stirring Wings",
                min_level=10,
                min_weird=0.1,
                min_favor={"King": 0.4, "Titania": 0.4},
                required_traits_any=["bloodline_angelic_latent"],
                grants_traits=["bloodline_angelic_stirring", "halo_manifest"],
                grants_abilities=["radiant_nova_minor", "healing_aura"],
                notes="Wings appear in visions, jumping bursts become feathered leaps.",
            ),
            _tier(
                id="angelic_awakened",
                label="Awakened Seraph",
                min_level=20,
                min_weird=0.15,
                min_favor={"King": 0.5, "Titania": 0.5},
                required_traits_any=["bloodline_angelic_stirring"],
                grants_traits=["bloodline_angelic_awakened", "wings_manifest"],
                grants_abilities=["radiant_nova_major", "flight_short", "shield_of_faith"],
                notes="Short-duration flight, strong radiant damage, defensive boons.",
            ),
            _tier(
                id="angelic_transcendent",
                label="Transcendent Avatar",
                min_level=35,
                min_weird=0.2,
                min_favor={"King": 0.6, "Titania": 0.6},
                required_traits_any=["bloodline_angelic_awakened"],
                grants_traits=["bloodline_angelic_transcendent"],
                grants_abilities=[
                    "flight_true",
                    "aura_of_peace",
                    "sword_of_light",
                    "angelic_form_once_per_long_rest",
                ],
                notes="Godlike moments: full angelic manifestation with severe story weight.",
            ),
        ],
    )


def make_bloodline_demonic_infernal() -> Bloodline:
    return Bloodline(
        id="bloodline_demonic_infernal",
        label="Infernal Heir",
        core_alignment_hint="Chaotic/Evil leaning (or at least ruthless)",
        patron_hint="Bottom, shadow patrons, or off-screen hell-powers",
        tiers=[
            _tier(
                id="infernal_latent",
                label="Whisper of Embers",
                min_level=1,
                min_weird=0.0,
                min_favor={"Bottom": 0.3},
                required_traits_any=["ambitious", "chaotic_neutral", "trickster"],
                grants_traits=["bloodline_infernal_latent"],
                grants_abilities=["hellfire_spark", "resistance_fire_minor"],
                notes="Dreams of fire, heat never feels quite dangerous.",
            ),
            _tier(
                id="infernal_stirring",
                label="Ashen Veins",
                min_level=10,
                min_weird=0.1,
                min_favor={"Bottom": 0.45},
                required_traits_any=["bloodline_infernal_latent"],
                grants_traits=["bloodline_infernal_stirring", "hell_touched"],
                grants_abilities=["hellfire_bolt", "fear_aura_minor"],
                notes="Eyes glow in darkness; enemies feel watched.",
            ),
            _tier(
                id="infernal_awakened",
                label="Devil of the Masquerade",
                min_level=20,
                min_weird=0.15,
                min_favor={"Bottom": 0.5},
                required_traits_any=["bloodline_infernal_stirring"],
                grants_traits=["bloodline_infernal_awakened", "horns_manifest"],
                grants_abilities=["hellfire_storm", "dominate_weaker_minds", "flight_winged_short"],
                notes="True horns, burning wings, and heavy demonic bargains.",
            ),
            _tier(
                id="infernal_transcendent",
                label="Cataclysmic Heir",
                min_level=35,
                min_weird=0.25,
                min_favor={"Bottom": 0.6},
                required_traits_any=["bloodline_infernal_awakened"],
                grants_traits=["bloodline_infernal_transcendent"],
                grants_abilities=[
                    "hellfire_cataclysm",
                    "greater_fear_aura",
                    "infernal_form_once_per_long_rest",
                ],
                notes="You become the catastrophe other gods notice.",
            ),
        ],
    )


def make_bloodline_forest_heir_druidic() -> Bloodline:
    return Bloodline(
        id="bloodline_forest_heir_druidic",
        label="Forest Heir",
        core_alignment_hint="Neutral/Good leaning, fey-adjacent",
        patron_hint="Titania, Queen, forest spirits",
        tiers=[
            _tier(
                id="forest_latent",
                label="Sapling Soul",
                min_level=1,
                min_weird=0.0,
                min_favor={"Titania": 0.3},
                required_traits_any=["forest_child", "class_druid"],
                grants_traits=["bloodline_forest_latent"],
                grants_abilities=["talk_to_plants_minor", "sense_tree_pain"],
                notes="Trees feel like old friends; dreams are full of leaves.",
            ),
            _tier(
                id="forest_stirring",
                label="Rooted Heart",
                min_level=8,
                min_weird=0.1,
                min_favor={"Titania": 0.4, "Queen": 0.3},
                required_traits_any=["bloodline_forest_latent"],
                grants_traits=["bloodline_forest_stirring"],
                grants_abilities=["regeneration_minor", "entangling_roots"],
                notes="Regeneration in forests; roots move slightly when you sleep.",
            ),
            _tier(
                id="forest_awakened",
                label="Ent-Blooded",
                min_level=18,
                min_weird=0.15,
                min_favor={"Titania": 0.5},
                required_traits_any=["bloodline_forest_stirring"],
                grants_traits=["bloodline_forest_awakened"],
                grants_abilities=["barkskin_form", "tree_stride", "call_woodland_spirits"],
                notes="Your skin resembles bark during stress; you step between trees.",
            ),
            _tier(
                id="forest_transcendent",
                label="Avatar of the Grove",
                min_level=30,
                min_weird=0.2,
                min_favor={"Titania": 0.6, "Queen": 0.4},
                required_traits_any=["bloodline_forest_awakened"],
                grants_traits=["bloodline_forest_transcendent"],
                grants_abilities=[
                    "grove_sanctuary",
                    "mass_regeneration",
                    "forest_avatar_once_per_long_rest",
                ],
                notes="You and the forest become mutually dependent mythic beings.",
            ),
        ],
    )


# --- evaluation -----------------------------------------------------------


def evaluate_bloodline_progress(
    bloodline: Bloodline,
    level: int,
    weird_level: float,
    favor: Dict[str, float],
    traits: List[str],
) -> Dict:
    """
    Given an agent's level, weird_level, favor and traits,
    figure out:
      - which tiers are currently active
      - which traits/abilities are granted
    """
    ts = set(traits)
    active_tiers: List[Dict] = []
    granted_traits: List[str] = []
    granted_abilities: List[str] = []

    for tier in bloodline.tiers:
        # level + weird check
        if level < tier.min_level:
            continue
        if weird_level < tier.min_weird:
            continue

        # favor requirements
        ok = True
        for patron, req in tier.min_favor.items():
            if favor.get(patron, 0.0) < req:
                ok = False
                break
        if not ok:
            continue

        # traits (any of required_traits_any)
        if tier.required_traits_any:
            if not (ts & set(tier.required_traits_any)):
                continue

        active_tiers.append(asdict(tier))
        granted_traits.extend(tier.grants_traits)
        granted_abilities.extend(tier.grants_abilities)

    return {
        "bloodline": bloodline.to_dict(),
        "active_tiers": active_tiers,
        "granted_traits": sorted(set(granted_traits)),
        "granted_abilities": sorted(set(granted_abilities)),
    }


if __name__ == "__main__":
    import json

    bl = make_bloodline_forest_heir_druidic()
    result = evaluate_bloodline_progress(
        bl,
        level=12,
        weird_level=0.12,
        favor={"Titania": 0.45, "Queen": 0.32},
        traits=["forest_child", "class_druid"],
    )
    print(json.dumps(result, indent=2))

