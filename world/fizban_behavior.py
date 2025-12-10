#!/usr/bin/env python3
"""
fizban_behavior.py

Behavior / strategy mixer for iterated game-theory strategies based on:
- alignment coordinates (law/chaos, good/evil)
- trait tags (class, personality, patron favor)
- patron favor scores
- trust affinity vs. current counterpart
- "weirdness" level (Titania/Bottom influence, strange states)

Output is a normalized strategy profile over:
  ["Copycat", "Cooperator", "Grudger", "Copykitten",
   "Detective", "Simpleton", "Random", "Cheater"]
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple


STRATEGIES: List[str] = [
    "Copycat",
    "Cooperator",
    "Grudger",
    "Copykitten",
    "Detective",
    "Simpleton",
    "Random",
    "Cheater",
]


@dataclass
class BehaviorInputs:
    name: str
    alignment_label: str
    alignment_coords: Tuple[float, float]  # (law_chaos, good_evil) in [-1,1]
    traits: List[str]
    favor: Dict[str, float]  # Titania/Oberon/Bottom/King/Queen/Lovers etc
    trust_affinity: float  # vs current counterpart, -1..+1 (roughly)
    weird_level: float  # 0..1 weird/strange state


@dataclass
class BehaviorProfile:
    name: str
    alignment_label: str
    alignment_coords: Tuple[float, float]
    traits: List[str]
    favor: Dict[str, float]
    trust_affinity: float
    weird_level: float
    strategy_weights: Dict[str, float]

    @property
    def strategy_profile_sorted(self) -> List[Tuple[str, float]]:
        """List of (strategy, weight) sorted descending by weight."""
        return sorted(
            self.strategy_weights.items(),
            key=lambda kv: kv[1],
            reverse=True,
        )


# --- helpers --------------------------------------------------------------


def _blank_weights() -> Dict[str, float]:
    return {s: 0.0 for s in STRATEGIES}


def _add_safe(weights: Dict[str, float], key: str, delta: float) -> None:
    if key in weights:
        weights[key] += delta


def _normalize(weights: Dict[str, float]) -> Dict[str, float]:
    # Clamp negatives to 0
    for k, v in list(weights.items()):
        if v < 0:
            weights[k] = 0.0
    total = sum(weights.values())
    if total <= 0:
        # fallback: flat distribution
        n = float(len(weights))
        return {k: 1.0 / n for k in weights}
    return {k: v / total for k, v in weights.items()}


# --- base alignment weights -----------------------------------------------


def _weights_from_alignment(coords: Tuple[float, float]) -> Dict[str, float]:
    """
    Map (law_chaos, good_evil) in [-1,1] to a base distribution.
    - Lawful + Good  => Copycat, Cooperator, Grudger
    - Chaotic + Neutral/Evil => Random, Copykitten, Detective, Cheater
    - True Neutral => more Simpleton/Random
    """
    law_chaos, good_evil = coords
    w = _blank_weights()

    lawful = max(0.0, law_chaos)
    chaotic = max(0.0, -law_chaos)
    good = max(0.0, good_evil)
    evil = max(0.0, -good_evil)
    neutral_axis = 1.0 - abs(good_evil)

    # Lawful: favors Copycat/Grudger
    _add_safe(w, "Copycat", 0.4 * lawful)
    _add_safe(w, "Grudger", 0.3 * lawful)
    _add_safe(w, "Cooperator", 0.2 * lawful)

    # Chaotic: Random/Copykitten/Detective/Cheater
    _add_safe(w, "Random", 0.4 * chaotic)
    _add_safe(w, "Copykitten", 0.25 * chaotic)
    _add_safe(w, "Detective", 0.2 * chaotic)
    _add_safe(w, "Cheater", 0.15 * chaotic)

    # Good: Cooperator/Copykitten, anti-Cheater
    _add_safe(w, "Cooperator", 0.4 * good)
    _add_safe(w, "Copykitten", 0.2 * good)
    _add_safe(w, "Cheater", -0.3 * good)

    # Evil: Cheater/Detective, anti-Cooperator
    _add_safe(w, "Cheater", 0.5 * evil)
    _add_safe(w, "Detective", 0.2 * evil)
    _add_safe(w, "Cooperator", -0.2 * evil)

    # True neutral: Simpleton/Random
    _add_safe(w, "Simpleton", 0.5 * neutral_axis)
    _add_safe(w, "Random", 0.3 * neutral_axis)

    return w


# --- trait modifiers ------------------------------------------------------


def _weights_from_traits(traits: List[str]) -> Dict[str, float]:
    w = _blank_weights()
    ts = set(traits)

    # Paladin / hero vibes
    if "class_paladin" in ts or "divine_knight" in ts or "hero" in ts:
        _add_safe(w, "Cooperator", 0.4)
        _add_safe(w, "Copycat", 0.2)
        _add_safe(w, "Grudger", 0.1)
        _add_safe(w, "Cheater", -0.4)

    # Rogue / trickster vibes
    if "class_rogue" in ts or "trickster" in ts or "trickster_heart" in ts:
        _add_safe(w, "Random", 0.4)
        _add_safe(w, "Copykitten", 0.2)
        _add_safe(w, "Detective", 0.2)
        _add_safe(w, "Cheater", 0.2)

    # Embraces chaos
    if "embraces_chaos" in ts or "chaotic_neutral" in ts:
        _add_safe(w, "Random", 0.3)
        _add_safe(w, "Copykitten", 0.1)
        _add_safe(w, "Simpleton", 0.05)

    # Strong loyalty / grudges
    if "lawful_good" in ts or "king_chosen" in ts or "oberon_favored" in ts:
        _add_safe(w, "Grudger", 0.3)
        _add_safe(w, "Copycat", 0.1)

    # Fey / weird / Titania
    if "titania_favored" in ts or "forest_child" in ts:
        _add_safe(w, "Copykitten", 0.15)
        _add_safe(w, "Detective", 0.1)

    # Bottom-favored = prankster
    if "bottom_favored" in ts or "bottom_chosen" in ts:
        _add_safe(w, "Random", 0.2)
        _add_safe(w, "Cheater", 0.15)

    return w


# --- patron favor modifiers -----------------------------------------------


def _weights_from_favor(favor: Dict[str, float]) -> Dict[str, float]:
    w = _blank_weights()

    titania = favor.get("Titania", 0.0)
    oberon = favor.get("Oberon", 0.0)
    bottom = favor.get("Bottom", 0.0)
    king = favor.get("King", 0.0)
    queen = favor.get("Queen", 0.0)
    lovers = favor.get("Lovers", 0.0)

    # Titania: playful, weird mercy
    _add_safe(w, "Copykitten", 0.4 * titania)
    _add_safe(w, "Detective", 0.2 * titania)

    # Oberon: contracts, grudges, order
    _add_safe(w, "Copycat", 0.3 * oberon)
    _add_safe(w, "Grudger", 0.3 * oberon)

    # Bottom: chaos & spectacle
    _add_safe(w, "Random", 0.4 * bottom)
    _add_safe(w, "Cheater", 0.3 * bottom)
    _add_safe(w, "Simpleton", 0.1 * bottom)

    # King: duty / cooperation
    _add_safe(w, "Cooperator", 0.4 * king)
    _add_safe(w, "Grudger", 0.1 * king)

    # Queen: weird research, subtle moves
    _add_safe(w, "Detective", 0.3 * queen)
    _add_safe(w, "Copykitten", 0.1 * queen)

    # Lovers: copykitten, cooperator, random romantic chaos
    _add_safe(w, "Copykitten", 0.3 * lovers)
    _add_safe(w, "Cooperator", 0.2 * lovers)
    _add_safe(w, "Random", 0.1 * lovers)

    return w


# --- trust + weird modifiers ----------------------------------------------


def _weights_from_trust(trust_affinity: float) -> Dict[str, float]:
    w = _blank_weights()
    # trust_affinity in [-1,1]
    if trust_affinity > 0:
        _add_safe(w, "Cooperator", 0.3 * trust_affinity)
        _add_safe(w, "Copycat", 0.2 * trust_affinity)
        _add_safe(w, "Grudger", -0.2 * trust_affinity)
        _add_safe(w, "Cheater", -0.3 * trust_affinity)
    elif trust_affinity < 0:
        a = abs(trust_affinity)
        _add_safe(w, "Grudger", 0.4 * a)
        _add_safe(w, "Cheater", 0.3 * a)
        _add_safe(w, "Cooperator", -0.3 * a)
    return w


def _weights_from_weird(weird_level: float) -> Dict[str, float]:
    w = _blank_weights()
    # weird_level in [0,1]. More weird => more Random/Detective/Copykitten, less strict plans.
    _add_safe(w, "Random", 0.3 * weird_level)
    _add_safe(w, "Detective", 0.2 * weird_level)
    _add_safe(w, "Copykitten", 0.2 * weird_level)
    _add_safe(w, "Copycat", -0.1 * weird_level)
    _add_safe(w, "Grudger", -0.1 * weird_level)
    return w


# --- public API -----------------------------------------------------------


def compute_behavior_profile(inputs: BehaviorInputs) -> BehaviorProfile:
    """Combine all signals into a final normalized strategy distribution."""
    w = _blank_weights()

    # Alignment backbone
    base = _weights_from_alignment(inputs.alignment_coords)
    for k, v in base.items():
        w[k] += v

    # Traits
    traits = _weights_from_traits(inputs.traits)
    for k, v in traits.items():
        w[k] += v

    # Favor
    fav = _weights_from_favor(inputs.favor)
    for k, v in fav.items():
        w[k] += v

    # Trust
    tr = _weights_from_trust(inputs.trust_affinity)
    for k, v in tr.items():
        w[k] += v

    # Weird
    weird = _weights_from_weird(inputs.weird_level)
    for k, v in weird.items():
        w[k] += v

    norm = _normalize(w)

    return BehaviorProfile(
        name=inputs.name,
        alignment_label=inputs.alignment_label,
        alignment_coords=inputs.alignment_coords,
        traits=list(inputs.traits),
        favor=dict(inputs.favor),
        trust_affinity=inputs.trust_affinity,
        weird_level=inputs.weird_level,
        strategy_weights=norm,
    )


def behavior_profile_to_dict(profile: BehaviorProfile) -> Dict:
    """Convenience for JSON output."""
    d = asdict(profile)
    # Also include sorted view
    d["strategy_profile_sorted"] = profile.strategy_profile_sorted
    return d


if __name__ == "__main__":
    # Tiny smoke test
    import json

    paladin_inputs = BehaviorInputs(
        name="Paladin",
        alignment_label="Lawful Good",
        alignment_coords=(1.0, 1.0),
        traits=["class_paladin", "hero", "lawful_good", "king_chosen"],
        favor={"King": 0.8, "Titania": 0.6},
        trust_affinity=0.2,
        weird_level=0.1,
    )
    profile = compute_behavior_profile(paladin_inputs)
    print(json.dumps(behavior_profile_to_dict(profile), indent=2))

