#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_behavior.py

Translate agent tags/traits/class into a strategy profile over
the iterated game-theory strategies:

- Copycat
- Cooperator
- Copykitten
- Grudger
- Simpleton
- Random
- Detective
- Cheater

Design:
- Start from a class/alignment baseline.
- Apply trait-based nudges (+/- weights).
- Renormalize to a 0..1 distribution.

This module is *pure* and does not mutate the agent. The main
sim engine can adopt it later as a policy adapter.
"""

from __future__ import annotations

from typing import Dict, List
import math


StrategyProfile = Dict[str, float]


ALL_STRATEGIES: List[str] = [
    "Copycat",
    "Cooperator",
    "Copykitten",
    "Grudger",
    "Simpleton",
    "Random",
    "Detective",
    "Cheater",
]


def _normalize(profile: StrategyProfile) -> StrategyProfile:
    total = sum(max(v, 0.0) for v in profile.values())
    if total <= 0:
        # fallback to uniform
        return {s: 1.0 / len(ALL_STRATEGIES) for s in ALL_STRATEGIES}
    return {k: max(v, 0.0) / total for k, v in profile.items()}


def baseline_for_agent(agent: Dict) -> StrategyProfile:
    """
    Very simple baselines by class + alignment label.
    """
    dnd_class = str(agent.get("class", {}).get("dnd_class", "")).lower()
    label = str(agent.get("alignment", {}).get("label", "")).lower()

    profile: StrategyProfile = {s: 1.0 for s in ALL_STRATEGIES}

    # Class baselines
    if dnd_class == "paladin":
        # Paladin: honorable, a bit stubborn
        profile.update(
            Copycat=1.8,
            Cooperator=1.8,
            Grudger=1.4,
            Copykitten=1.2,
            Simpleton=0.8,
            Random=0.6,
            Detective=1.0,
            Cheater=0.2,
        )
    elif dnd_class == "rogue":
        # Rogue: opportunistic, playful
        profile.update(
            Copycat=1.1,
            Cooperator=0.9,
            Grudger=0.8,
            Copykitten=1.5,
            Simpleton=0.7,
            Random=1.6,
            Detective=1.3,
            Cheater=1.3,
        )
    else:
        # Generic adventurer
        profile.update(
            Copycat=1.2,
            Cooperator=1.2,
            Grudger=1.0,
            Copykitten=1.0,
            Simpleton=1.0,
            Random=1.0,
            Detective=1.0,
            Cheater=0.8,
        )

    # Alignment nudges
    if "lawful" in label:
        profile["Copycat"] += 0.4
        profile["Grudger"] += 0.2
        profile["Random"] -= 0.2
        profile["Cheater"] -= 0.2
    if "chaotic" in label:
        profile["Random"] += 0.5
        profile["Copykitten"] += 0.3
        profile["Simpleton"] += 0.1
    if "good" in label:
        profile["Cooperator"] += 0.4
        profile["Cheater"] -= 0.3
    if "evil" in label:
        profile["Cheater"] += 0.5
        profile["Grudger"] += 0.3
        profile["Cooperator"] -= 0.3

    return _normalize(profile)


def infer_traits(agent: Dict) -> List[str]:
    """
    Infer a trait set from tags + class + misc state.

    This is intentionally messy + expandable. It just creates
    a vocabulary we can use to drive behavior.
    """
    traits: List[str] = []

    tags = [str(t).lower() for t in agent.get("tags", [])]
    dnd_class = str(agent.get("class", {}).get("dnd_class", "")).lower()
    label = str(agent.get("alignment", {}).get("label", "")).lower()

    traits.extend(tags)

    if dnd_class:
        traits.append(f"class:{dnd_class}")

    if "lawful" in label:
        traits.append("lawful")
    if "chaotic" in label:
        traits.append("chaotic")
    if "good" in label:
        traits.append("good")
    if "evil" in label:
        traits.append("evil")

    # Future: pull traits from level-tree unlocks, e.g. node.effects.traits_add

    # Deduplicate while preserving order
    seen = set()
    unique: List[str] = []
    for t in traits:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def apply_traits_to_profile(traits: List[str], profile: StrategyProfile) -> StrategyProfile:
    """
    Apply trait-based nudges to the profile.
    """
    p = dict(profile)

    def bump(key: str, delta: float) -> None:
        if key in p:
            p[key] = max(0.0, p[key] + delta)

    low_traits = [t.lower() for t in traits]

    # Trickster/chaotic_neutral → more playful defection and probing
    if "trickster" in low_traits or "chaotic_neutral" in low_traits or "class:rogue" in low_traits:
        bump("Random", 0.4)
        bump("Copykitten", 0.3)
        bump("Detective", 0.2)
        bump("Cheater", 0.2)

    # Heroic / lawful_good → more cooperation & grudging punishment
    if "hero" in low_traits or "lawful_good" in low_traits or "class:paladin" in low_traits:
        bump("Cooperator", 0.4)
        bump("Copycat", 0.3)
        bump("Grudger", 0.3)
        bump("Cheater", -0.3)

    # Forest / vanguard traits (once unlocked from trees)
    if "forest_vanguard" in low_traits or "grove_guardian" in low_traits:
        bump("Cooperator", 0.2)
        bump("Grudger", 0.1)

    # Weird / Bottom-adjacent vibes → more Random and Simpleton
    if "weird" in low_traits:
        bump("Random", 0.3)
        bump("Simpleton", 0.2)

    # Merchant/contract → more Copycat and Detective (careful tit-for-tat, investigate)
    if "merchant" in low_traits or "contract" in low_traits:
        bump("Copycat", 0.3)
        bump("Detective", 0.3)

    # Seductive/succubus-style (for future demonic bloodline)
    if "succubus" in low_traits or "seducer" in low_traits:
        bump("Copykitten", 0.4)
        bump("Detective", 0.2)
        bump("Cheater", 0.2)

    return _normalize(p)


def build_strategy_profile(agent: Dict) -> Dict[str, object]:
    """
    Public helper: baseline → traits → final profile, plus metadata.
    """
    traits = infer_traits(agent)
    base = baseline_for_agent(agent)
    final = apply_traits_to_profile(traits, base)

    # For UI/debug: sort by weight desc
    sorted_items = sorted(final.items(), key=lambda kv: kv[1], reverse=True)

    return {
        "class": agent.get("class", {}).get("dnd_class"),
        "alignment_label": agent.get("alignment", {}).get("label"),
        "traits": traits,
        "strategy_profile": final,
        "strategy_profile_sorted": sorted_items,
    }

