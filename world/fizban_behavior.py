#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_behavior.py

Behavior engine for strategies (Copycat, Cooperator, Cheater, etc.)

This version:
- Uses alignment (law/chaos, good/evil)
- Uses traits derived from:
  - class
  - favor with gods
  - level-tree unlocks
- Returns a weight distribution over Nicky Case-style strategies.

The goal is *illusion of personality*:
Paladin + Titania + Oath => more Cooperator/Grudger/Copycat
Puck + Bottom + Lovers => more Random/Copykitten/Cheater
"""

from __future__ import annotations

from typing import Dict, Any, List, Tuple

from fizban_alignment import ALIGNMENT_MAP
from fizban_traits import derive_traits_for_agent


STRATEGIES: List[str] = [
    "Copycat",
    "Cooperator",
    "Grudger",
    "Copykitten",
    "Simpleton",
    "Random",
    "Detective",
    "Cheater",
]


def _init_weights() -> Dict[str, float]:
    return {s: 1.0 for s in STRATEGIES}


def _apply_alignment_influence(
    weights: Dict[str, float], agent: Dict[str, Any]
) -> None:
    align = (agent.get("alignment") or {}).get("label")
    if align is None:
        # try to reconstruct from map if needed
        law = (agent.get("alignment") or {}).get("law_chaos")
        good = (agent.get("alignment") or {}).get("good_evil")
        key = f"{law}_{good}".upper()
        align = ALIGNMENT_MAP.get(key, {}).get("label")

    label = (align or "").upper()

    # Lawful => Copycat, Grudger
    if "LAWFUL" in label:
        weights["Copycat"] *= 1.4
        weights["Grudger"] *= 1.3

    # Chaotic => Random, Cheater, Copykitten
    if "CHAOTIC" in label:
        weights["Random"] *= 1.4
        weights["Cheater"] *= 1.25
        weights["Copykitten"] *= 1.2

    # Good => Cooperator, Copykitten
    if "GOOD" in label:
        weights["Cooperator"] *= 1.4
        weights["Copykitten"] *= 1.2
        # soften pure Cheater
        weights["Cheater"] *= 0.8

    # Evil => Cheater, Detective
    if "EVIL" in label:
        weights["Cheater"] *= 1.4
        weights["Detective"] *= 1.2
        # soften Cooperator
        weights["Cooperator"] *= 0.85

    # Neutral in either axis => Random + Simpleton slightly up
    if "NEUTRAL" in label and "TRUE" in label:
        weights["Random"] *= 1.1
        weights["Simpleton"] *= 1.1


def _apply_trait_influence(
    weights: Dict[str, float], trait_summary: Dict[str, Any]
) -> None:
    traits = set(trait_summary.get("traits") or [])

    def bump(names: List[str], factor: float) -> None:
        for n in names:
            if n in weights:
                weights[n] *= factor

    # Class-based behavior:
    if "class_paladin" in traits:
        bump(["Cooperator", "Copycat", "Grudger"], 1.25)
        bump(["Cheater", "Random"], 0.8)

    if "class_rogue" in traits or "trickster_heart" in traits:
        bump(["Random", "Detective", "Cheater"], 1.15)

    if "class_druid" in traits or "forest_bloodline" in traits:
        bump(["Copykitten", "Simpleton"], 1.2)

    if "class_bard" in traits or "story_weaver" in traits:
        bump(["Copykitten", "Random"], 1.15)

    if "class_barbarian" in traits or "rage_bloodline" in traits:
        bump(["Cheater", "Simpleton"], 1.15)
        bump(["Detective"], 0.9)

    # Oath / tree-based:
    if "oathbound" in traits or "vow_keeper" in traits:
        bump(["Grudger", "Copycat"], 1.3)

    if "forest_sentinel" in traits or "forest_guardian" in traits:
        bump(["Cooperator", "Copykitten"], 1.2)

    # Favor-based:
    if "titania_favored" in traits or "titania_chosen" in traits:
        bump(["Copykitten", "Simpleton"], 1.2)
        bump(["Random"], 1.05)

    if "oberon_favored" in traits or "oberon_chosen" in traits:
        bump(["Detective", "Copycat"], 1.25)

    if "bottom_favored" in traits or "bottom_chosen" in traits:
        bump(["Random", "Cheater"], 1.3)

    if "lovers_favored" in traits or "lover_bonded" in traits:
        bump(["Cooperator", "Copykitten"], 1.25)

    if "king_favored" in traits or "king_chosen" in traits:
        bump(["Grudger"], 1.2)

    if "queen_favored" in traits or "queen_chosen" in traits:
        bump(["Random", "Detective"], 1.15)

    # Spy network / weird research pushes toward "meta" strategies
    if "spy_network_friend" in traits:
        bump(["Detective"], 1.2)


def _normalize(weights: Dict[str, float]) -> Dict[str, float]:
    total = sum(max(v, 0.0) for v in weights.values())
    if total <= 0:
        # fallback to uniform
        n = float(len(weights))
        return {k: 1.0 / n for k in weights.keys()}
    return {k: max(v, 0.0) / total for k, v in weights.items()}


def compute_behavior_profile(agent: Dict[str, Any]) -> Dict[str, Any]:
    """
    Public API.

    Returns:
    {
      "strategy_profile": {strategy: float},
      "strategy_profile_sorted": [["Copycat", 0.3], ...],
      "traits": [...],
      "debug": {...}
    }
    """
    weights = _init_weights()

    # Derive traits + favor snapshot
    trait_summary = derive_traits_for_agent(agent)

    # Alignment and traits both push on weights
    _apply_alignment_influence(weights, agent)
    _apply_trait_influence(weights, trait_summary)

    profile = _normalize(weights)
    sorted_profile: List[Tuple[str, float]] = sorted(
        profile.items(), key=lambda kv: kv[1], reverse=True
    )

    return {
        "strategy_profile": profile,
        "strategy_profile_sorted": sorted_profile,
        "traits": trait_summary["traits"],
        "debug": {
            "trait_sources": trait_summary["sources"],
            "favor": trait_summary["favor"],
        },
    }

