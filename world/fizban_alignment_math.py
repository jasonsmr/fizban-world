#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_alignment_math.py

Numeric backbone for D&D-style alignment in the Fizban world.

- Represent each alignment as a point on a 2D grid:
    law_chaos axis:  LAWFUL = +1, NEUTRAL = 0, CHAOTIC = -1
    good_evil axis:  GOOD   = +1, NEUTRAL = 0, EVIL     = -1

- Provide:
    * alignment_to_axes(label) -> (law_chaos, good_evil)
    * axes_to_alignment(law_chaos, good_evil) -> label string
    * alignment_distance(a, b)  (Euclidean)
    * alignment_compatibility(a, b) in [0, 1]
    * suggest_default_strategy(label) -> Ncase-like strategy tag
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Dict, Tuple

# --- Canonical alignment labels (9-point grid) ---

ALIGNMENTS = [
    "Lawful Good",
    "Neutral Good",
    "Chaotic Good",
    "Lawful Neutral",
    "True Neutral",
    "Chaotic Neutral",
    "Lawful Evil",
    "Neutral Evil",
    "Chaotic Evil",
]

# Axes: (law_chaos, good_evil)
# LAWFUL = +1, NEUTRAL = 0, CHAOTIC = -1
# GOOD   = +1, NEUTRAL = 0, EVIL    = -1
_ALIGNMENT_TO_AXES: Dict[str, Tuple[int, int]] = {
    "Lawful Good": (1, 1),
    "Neutral Good": (0, 1),
    "Chaotic Good": (-1, 1),
    "Lawful Neutral": (1, 0),
    "True Neutral": (0, 0),
    "Chaotic Neutral": (-1, 0),
    "Lawful Evil": (1, -1),
    "Neutral Evil": (0, -1),
    "Chaotic Evil": (-1, -1),
}

_AXES_TO_ALIGNMENT: Dict[Tuple[int, int], str] = {
    v: k for k, v in _ALIGNMENT_TO_AXES.items()
}


@dataclass(frozen=True)
class AlignmentPoint:
    """
    A numeric representation of alignment on the 2D grid.

    law_chaos: +1 (Lawful), 0 (Neutral), -1 (Chaotic)
    good_evil: +1 (Good),   0 (Neutral), -1 (Evil)
    """
    label: str
    law_chaos: int
    good_evil: int

    @property
    def as_tuple(self) -> Tuple[int, int]:
        return (self.law_chaos, self.good_evil)


def normalize_label(label: str) -> str:
    """Normalize alignment strings to canonical form."""
    s = " ".join(label.strip().split())
    s = s.title()
    # special case: 'True Neutral'
    if s in ("Neutral Neutral", "Neutral"):
        s = "True Neutral"
    return s


def alignment_to_axes(label: str) -> AlignmentPoint:
    """
    Map a human-readable alignment label to an AlignmentPoint.
    Raises ValueError if unknown.
    """
    canon = normalize_label(label)
    if canon not in _ALIGNMENT_TO_AXES:
        raise ValueError(f"Unknown alignment label: {label!r}")
    x, y = _ALIGNMENT_TO_AXES[canon]
    return AlignmentPoint(label=canon, law_chaos=x, good_evil=y)


def axes_to_alignment(law_chaos: int, good_evil: int) -> AlignmentPoint:
    """
    Snap a numeric (law_chaos, good_evil) pair back to the nearest canonical grid point.
    The inputs should be in [-1, 0, +1] but we clamp if they drift.
    """
    def clamp(v: int) -> int:
        if v > 0:
            return 1
        if v < 0:
            return -1
        return 0

    x = clamp(int(round(law_chaos)))
    y = clamp(int(round(good_evil)))
    label = _AXES_TO_ALIGNMENT.get((x, y), "True Neutral")
    return AlignmentPoint(label=label, law_chaos=x, good_evil=y)


def alignment_distance(a: str, b: str) -> float:
    """
    Euclidean distance between two alignments on the 2D grid.

    Max distance is sqrt( (1 - -1)^2 + (1 - -1)^2 ) = sqrt(8) ~ 2.828,
    i.e. Lawful Good vs Chaotic Evil.
    """
    pa = alignment_to_axes(a)
    pb = alignment_to_axes(b)
    dx = pa.law_chaos - pb.law_chaos
    dy = pa.good_evil - pb.good_evil
    return sqrt(dx * dx + dy * dy)


def alignment_compatibility(a: str, b: str) -> float:
    """
    Convert distance into a compatibility score in [0, 1].

    1.0  => identical alignment
    ~0.0 => opposite corners (Lawful Good vs Chaotic Evil, etc)
    """
    d = alignment_distance(a, b)
    # max_dist = sqrt(8); we normalize and invert
    max_dist = sqrt(8.0)
    # Protect from rounding > 1.0
    frac = min(d / max_dist, 1.0)
    return 1.0 - frac


def suggest_default_strategy(label: str) -> str:
    """
    Suggest a Nicky Case-style iterated game strategy tag
    based on D&D alignment.
    (No code from Ncase; this is just conceptual mapping.)

    Examples:
        Lawful Good     -> "Copykitten" (forgiving tit-for-tat)
        Neutral Good    -> "Cooperator"
        Chaotic Good    -> "Simpleton" (leans trusting but swingy)
        Lawful Neutral  -> "Grudger"
        True Neutral    -> "Random"
        Chaotic Neutral -> "Random"
        Lawful Evil     -> "Detective"
        Neutral Evil    -> "Cheater"
        Chaotic Evil    -> "Cheater"
    """
    canon = normalize_label(label)
    if canon == "Lawful Good":
        return "Copykitten"
    if canon == "Neutral Good":
        return "Cooperator"
    if canon == "Chaotic Good":
        return "Simpleton"

    if canon == "Lawful Neutral":
        return "Grudger"
    if canon == "True Neutral":
        return "Random"
    if canon == "Chaotic Neutral":
        return "Random"

    if canon == "Lawful Evil":
        return "Detective"
    if canon in ("Neutral Evil", "Chaotic Evil"):
        return "Cheater"

    # Fallback (shouldn't happen if labels are canonical)
    return "Random"


def demo_grid() -> None:
    """
    Small human-readable printout of the 3x3 alignment grid with coords.
    Useful for quick sanity checks in REPL.
    """
    rows = [
        ["Lawful Good", "Neutral Good", "Chaotic Good"],
        ["Lawful Neutral", "True Neutral", "Chaotic Neutral"],
        ["Lawful Evil", "Neutral Evil", "Chaotic Evil"],
    ]
    for row in rows:
        line = []
        for label in row:
            p = alignment_to_axes(label)
            line.append(f"{p.label} ({p.law_chaos:+d},{p.good_evil:+d})")
        print(" | ".join(line))

