#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_trust_math.py

Trust + bounce-back math for Fizban.

- Uses numeric D&D alignment compatibility from fizban_alignment_math
- Tracks per-pair trust state:
    * affinity   : [-1, +1]   (how much I trust/like you)
    * gossip_bias: [-1, +1]   (how rumor/third-party influence is skewing this)
    * awe        : [0, 1]     (how impressed / starstruck I am)
    * boredom    : [0, 1]     (how bored / complacent I am)
    * last_outcome: "CC", "CD", "DC", "DD" or ""
    * betrayal_count    : >= 0 (how many real betrayals I feel from you)
    * cooperation_streak: >= 0 (how many recent good rounds in a row)

- Provides:
    init_trust_state(my_alignment, other_alignment, *, base_gossip=0.0) -> TrustState
    update_trust_state(state, outcome, *, awe_boost=0.0, boredom_boost=0.0,
                       gossip_delta=0.0, bounce=0.1) -> (TrustState, deltas)

Where:
    outcome is from my point of view:
        "CC" = we both cooperated
        "CD" = I cooperated, you defected (you betrayed me)
        "DC" = I defected, you cooperated (I exploited you)
        "DD" = both defected
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Tuple

from fizban_alignment_math import (
    alignment_compatibility,
    suggest_default_strategy,
    normalize_label,
)


@dataclass
class TrustState:
    # Core weights
    affinity: float       # [-1, +1]
    gossip_bias: float    # [-1, +1]
    awe: float            # [0, 1]
    boredom: float        # [0, 1]

    # Meta
    last_outcome: str     # "CC","CD","DC","DD",""

    # Counters
    betrayal_count: float
    cooperation_streak: float

    # Optional: mirror the default strategy we expect from the other
    expected_strategy: str

    def to_dict(self) -> Dict[str, object]:
        """Serialize to a dict suitable for JSON."""
        return asdict(self)


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def compatibility_to_affinity(comp: float) -> float:
    """
    Map compatibility [0,1] -> affinity [-1,1].
    0.5 becomes neutral 0.0, above 0.5 positive, below 0.5 negative.
    """
    return 2.0 * comp - 1.0


def init_trust_state(
    my_alignment: str,
    other_alignment: str,
    *,
    base_gossip: float = 0.0,
    base_awe: float = 0.0,
    base_boredom: float = 0.0,
) -> TrustState:
    """
    Initialize trust toward another agent based purely on alignments + optional biases.

    Example:
        Paladin (Lawful Good) seeing Puck (Chaotic Neutral)
        => low compatibility, slightly negative affinity.
    """
    comp = alignment_compatibility(my_alignment, other_alignment)
    affinity = compatibility_to_affinity(comp)

    # Keep base values within their ranges
    gossip = clamp(base_gossip, -1.0, 1.0)
    awe = clamp(base_awe, 0.0, 1.0)
    boredom = clamp(base_boredom, 0.0, 1.0)

    expected_strat = suggest_default_strategy(normalize_label(other_alignment))

    return TrustState(
        affinity=affinity,
        gossip_bias=gossip,
        awe=awe,
        boredom=boredom,
        last_outcome="",
        betrayal_count=0.0,
        cooperation_streak=0.0,
        expected_strategy=expected_strat,
    )


def _outcome_effects(
    state: TrustState,
    outcome: str,
) -> Tuple[float, float, float]:
    """
    For a single round outcome, compute:
        delta_affinity, delta_betrayal, delta_coop_streak

    outcome is from *my* POV:
        "CC" : mutual cooperation
        "CD" : I cooperated, they defected  -> I feel betrayed
        "DC" : I defected, they cooperated -> I feel a bit guilty (or emboldened)
        "DD" : mutual defection
    """
    outcome = outcome.upper()
    if outcome not in ("CC", "CD", "DC", "DD"):
        raise ValueError(f"Unknown outcome: {outcome!r}")

    base_step = 0.15  # how much a single round can shift affinity

    if outcome == "CC":
        # trust reinforcement
        return (+base_step, 0.0, +1.0)

    if outcome == "CD":
        # They stabbed me in the back; drop affinity hard
        return (-2.0 * base_step, +1.0, 0.0)

    if outcome == "DC":
        # I exploited them; may slightly *lower* my affinity (guilt) or
        # slightly raise (if I'm evil). For now, small negative.
        return (-0.05, 0.0, 0.0)

    if outcome == "DD":
        # both defect; cynicism rises a bit, so small affinity drop, reset streak
        return (-0.1, 0.0, 0.0)

    # unreachable
    return (0.0, 0.0, 0.0)


def update_trust_state(
    state: TrustState,
    outcome: str,
    *,
    awe_boost: float = 0.0,
    boredom_boost: float = 0.0,
    gossip_delta: float = 0.0,
    bounce: float = 0.1,
) -> Tuple[TrustState, Dict[str, float]]:
    """
    Update a TrustState in-place-ish (returns a new copy) given a round outcome.

    - outcome: "CC","CD","DC","DD" from *my* point of view
    - awe_boost / boredom_boost:
        short-term emotional modifiers from the encounter (e.g. heroic act raises awe)
    - gossip_delta:
        external adjustment from wbwwb-style gossip / media
    - bounce:
        how fast things move back toward neutral over time (0.0=no bounce, 1.0=fast)

    Returns:
        (new_state, deltas) where deltas = {
            "delta_affinity": ...,
            "delta_betrayal": ...,
            "delta_coop_streak": ...,
            "delta_grace": ...,
            "delta_mental_strain": ...,
        }
    """
    outcome = outcome.upper()
    daff, dbetray, dcoop = _outcome_effects(state, outcome)

    # Start from previous
    affinity = state.affinity
    betrayal = state.betrayal_count
    coop_streak = state.cooperation_streak

    # Apply outcome effects
    affinity += daff
    betrayal += dbetray
    if outcome == "CC":
        coop_streak += dcoop
    else:
        # any non-perfect round resets streak
        coop_streak = 0.0

    # Apply gossip
    gossip = clamp(state.gossip_bias + gossip_delta, -1.0, 1.0)

    # Awe/Boredom short-term tweaks
    awe = clamp(state.awe + awe_boost, 0.0, 1.0)
    boredom = clamp(state.boredom + boredom_boost, 0.0, 1.0)

    # Bounce-back toward neutral (0 affinity) over time
    # If bounce > 0, slowly move affinity toward 0 depending on boredom (more bored -> faster decay)
    if bounce > 0.0:
        decay_factor = bounce * (0.5 + 0.5 * boredom)  # boredom speeds up "meh"
        affinity -= decay_factor * affinity

    # Clamp affinity range
    affinity = clamp(affinity, -1.0, 1.0)

    # Map betrayal / coop to fate deltas (Titania's Grace) heuristically:
    # - repeated betrayal increases mental strain, lowers grace
    # - cooperation streak increases grace, reduces strain
    delta_mental_strain = 0.1 * dbetray - 0.02 * dcoop
    delta_grace = 0.05 * dcoop - 0.05 * dbetray

    new_state = TrustState(
        affinity=affinity,
        gossip_bias=gossip,
        awe=awe,
        boredom=boredom,
        last_outcome=outcome,
        betrayal_count=betrayal,
        cooperation_streak=coop_streak,
        expected_strategy=state.expected_strategy,
    )

    deltas = {
        "delta_affinity": daff,
        "delta_betrayal": dbetray,
        "delta_coop_streak": dcoop,
        "delta_grace": delta_grace,
        "delta_mental_strain": delta_mental_strain,
    }
    return new_state, deltas

