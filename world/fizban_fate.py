#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_fate.py

Titania's Grace / Fate engine for Fizban.

- FateState:
    grace        : [0,1]   (how favored you are by Titania / "good fortune")
    bounce_back  : [0,1]   (how quickly you emotionally recover)
    mental_strain: [0,1]   (stress / weirdness load)
    weird_mode   : bool    (special state: too stressed or too awestruck)

- Functions:
    init_fate_state(alignment_label) -> FateState
    apply_trust_deltas_to_fate(fate, deltas, awe, boredom) -> FateState
    roll_destiny(fate, alignment_label, dc=12) -> dict

The idea:
    - Trust engine emits small deltas:
        delta_grace, delta_mental_strain
    - Fate integrates those over time, applies decay, and flips weird_mode on/off.
    - roll_destiny acts like a D&D d20 roll modified by grace/strain,
      with advantage/disadvantage when weird_mode is active.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any
import random

from fizban_alignment_math import normalize_label


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


@dataclass
class FateState:
    grace: float         # [0,1]
    bounce_back: float   # [0,1]
    mental_strain: float # [0,1]
    weird_mode: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _alignment_baseline(alignment_label: str) -> Dict[str, float]:
    """
    Simple heuristic baselines for fate based on alignment.
    We can make this more elaborate later (e.g. LG more grace, CE more strain).
    """
    label = normalize_label(alignment_label)
    base = {
        "grace": 0.5,
        "bounce_back": 0.5,
        "mental_strain": 0.1,
    }

    if label == "Lawful Good":
        base["grace"] = 0.6
        base["bounce_back"] = 0.6
        base["mental_strain"] = 0.1
    elif label == "Chaotic Good":
        base["grace"] = 0.55
        base["bounce_back"] = 0.7
        base["mental_strain"] = 0.15
    elif label == "Neutral Good":
        base["grace"] = 0.58
        base["bounce_back"] = 0.55
        base["mental_strain"] = 0.12
    elif label == "Lawful Evil":
        base["grace"] = 0.45
        base["bounce_back"] = 0.5
        base["mental_strain"] = 0.2
    elif label == "Neutral Evil":
        base["grace"] = 0.4
        base["bounce_back"] = 0.45
        base["mental_strain"] = 0.25
    elif label == "Chaotic Evil":
        base["grace"] = 0.35
        base["bounce_back"] = 0.6
        base["mental_strain"] = 0.3
    elif label == "Chaotic Neutral":
        base["grace"] = 0.5
        base["bounce_back"] = 0.7
        base["mental_strain"] = 0.2
    elif label == "Lawful Neutral":
        base["grace"] = 0.52
        base["bounce_back"] = 0.55
        base["mental_strain"] = 0.15
    elif label == "True Neutral":
        base["grace"] = 0.5
        base["bounce_back"] = 0.5
        base["mental_strain"] = 0.15

    return base


def init_fate_state(alignment_label: str) -> FateState:
    """
    Initialize FateState based on alignment.
    """
    base = _alignment_baseline(alignment_label)
    return FateState(
        grace=base["grace"],
        bounce_back=base["bounce_back"],
        mental_strain=base["mental_strain"],
        weird_mode=False,
    )


def apply_trust_deltas_to_fate(
    fate: FateState,
    deltas: Dict[str, float],
    awe: float,
    boredom: float,
) -> FateState:
    """
    Integrate trust deltas into FateState.

    Inputs:
      - deltas: from update_trust_state(...)[1], contains:
          "delta_grace", "delta_mental_strain"
      - awe, boredom: [0,1] current short-term emotional levels

    Behavior:
      - small drift of grace toward 0.5 baseline
      - apply delta_grace / delta_mental_strain
      - awe slightly reduces strain, boredom increases strain
      - bounce_back adjusts based on grace/strain
      - weird_mode flips on if mental_strain is high or (awe + strain) is high
    """
    g = fate.grace
    s = fate.mental_strain
    b = fate.bounce_back

    d_grace = deltas.get("delta_grace", 0.0)
    d_strain = deltas.get("delta_mental_strain", 0.0)

    # Soft drift of grace toward 0.5 (neutral) over time
    g += 0.02 * (0.5 - g)

    # Apply trust deltas
    g += d_grace
    s += d_strain

    # Awe reduces strain a little; boredom increases it.
    s -= 0.03 * awe
    s += 0.03 * boredom

    # Clamp ranges
    g = clamp(g, 0.0, 1.0)
    s = clamp(s, 0.0, 1.0)

    # Adjust bounce_back:
    #   more grace, less strain => faster bounce
    #   more strain => slower bounce
    target_bounce = 0.3 + 0.7 * g - 0.5 * s   # range approx [0,1], un-clamped
    b += 0.1 * (target_bounce - b)
    b = clamp(b, 0.0, 1.0)

    # Weird mode: high strain or high combo of awe+strain
    weird = s > 0.7 or (awe + s) > 1.2

    return FateState(
        grace=g,
        bounce_back=b,
        mental_strain=s,
        weird_mode=weird,
    )


def roll_destiny(
    fate: FateState,
    alignment_label: str,
    dc: int = 12,
) -> Dict[str, Any]:
    """
    Do a D&D-style destiny roll:
      - base d20 roll
      - grace_mod: from grace (more grace => higher mod)
      - strain_penalty: from mental_strain
      - if weird_mode:
          * positive grace-strain: "advantage" (roll 2, take higher)
          * negative grace-strain: "disadvantage" (roll 2, take lower)
    Returns a dict with full breakdown.
    """
    # Alignment can later tweak things if we want, but for now it's just recorded.
    _ = normalize_label(alignment_label)

    # Map grace [0,1] -> modifier roughly in [-2, +2]
    grace_mod = int(round((fate.grace - 0.5) * 4.0))
    # Strain penalty 0..2
    strain_penalty = int(round(fate.mental_strain * 2.0))

    roll_type = "normal"
    if fate.weird_mode:
        net = fate.grace - fate.mental_strain
        if net >= 0:
            roll_type = "advantage"
        else:
            roll_type = "disadvantage"

    def roll_d20():
        return random.randint(1, 20)

    if roll_type == "normal":
        base_roll = roll_d20()
    else:
        r1 = roll_d20()
        r2 = roll_d20()
        if roll_type == "advantage":
            base_roll = max(r1, r2)
        else:
            base_roll = min(r1, r2)

    total = base_roll + grace_mod - strain_penalty
    success = total >= dc

    return {
        "alignment": alignment_label,
        "base_roll": base_roll,
        "grace_mod": grace_mod,
        "strain_penalty": strain_penalty,
        "total": total,
        "dc": dc,
        "success": success,
        "roll_type": roll_type,
        "fate_snapshot": fate.to_dict(),
    }

