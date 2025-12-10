#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_alignment_math_demo.py

Quick demo of the numeric alignment backbone:
- prints the alignment grid with axes
- prints a compatibility matrix
- shows a couple of specific examples
"""

from __future__ import annotations

import json
from typing import List

from fizban_alignment_math import (
    ALIGNMENTS,
    alignment_to_axes,
    alignment_distance,
    alignment_compatibility,
    suggest_default_strategy,
    demo_grid,
)


def main() -> int:
    print("=== Alignment Grid ===")
    demo_grid()
    print()

    # Compatibility matrix
    print("=== Compatibility Matrix (0.00 - 1.00) ===")
    header = " " * 18 + " ".join(f"{a[:3]:>6}" for a in ALIGNMENTS)
    print(header)
    for a in ALIGNMENTS:
        row_vals: List[str] = []
        for b in ALIGNMENTS:
            c = alignment_compatibility(a, b)
            row_vals.append(f"{c:6.2f}")
        print(f"{a:<18} " + " ".join(row_vals))
    print()

    # A couple of examples wired to your lore
    examples = []

    paladin_align = "Lawful Good"
    puck_align = "Chaotic Neutral"
    thief_align = "Chaotic Evil"

    for name, a, b in [
        ("Paladin vs Puck", paladin_align, puck_align),
        ("Paladin vs Thief", paladin_align, thief_align),
        ("Puck vs Thief", puck_align, thief_align),
    ]:
        pa = alignment_to_axes(a)
        pb = alignment_to_axes(b)
        dist = alignment_distance(a, b)
        comp = alignment_compatibility(a, b)
        examples.append(
            {
                "pair": name,
                "a": {
                    "label": pa.label,
                    "coords": pa.as_tuple,
                    "default_strategy": suggest_default_strategy(pa.label),
                },
                "b": {
                    "label": pb.label,
                    "coords": pb.as_tuple,
                    "default_strategy": suggest_default_strategy(pb.label),
                },
                "distance": dist,
                "compatibility": comp,
            }
        )

    print("=== Example Pairs ===")
    print(json.dumps(examples, indent=2))
    print()
    print("Note: compatibility ~1.0 means very aligned; ~0.0 means opposed.\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

