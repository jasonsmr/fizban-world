#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_dnd_mapping.py
---------------------

D&D alignment + class mapping helpers for Fizban-World.

- Loads world/dnd_alignment_mapping.json
- Provides:
    * lookup_alignment_entry(alignment_config)
    * strategy_mix_for_alignment(alignment_config)
    * suggest_alignment_for_class(dnd_class, fallback_alignment)
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from fizban_agent_config import AlignmentConfig


BASE_DIR = Path(__file__).resolve().parent
MAPPING_FILE = BASE_DIR / "dnd_alignment_mapping.json"


class DndMappingError(RuntimeError):
    pass


def _load_mapping() -> Dict[str, Any]:
    if not MAPPING_FILE.is_file():
        raise DndMappingError(f"Mapping file not found: {MAPPING_FILE}")
    try:
        data = json.loads(MAPPING_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        raise DndMappingError(f"Failed to parse {MAPPING_FILE}: {e}")
    return data


def _normalize_weights(items: List[Dict[str, Any]], key: str = "weight") -> List[Dict[str, Any]]:
    total = sum(max(0.0, float(x.get(key, 0.0))) for x in items)
    if total <= 0:
        # if everything is zero, just spread evenly
        n = len(items)
        if n == 0:
            return []
        w = 1.0 / n
        return [{**x, key: w} for x in items]
    return [{**x, key: float(x.get(key, 0.0)) / total} for x in items]


def lookup_alignment_entry(aln: AlignmentConfig) -> Optional[Dict[str, Any]]:
    """
    Find the alignment metadata entry for a given AlignmentConfig.
    """
    mapping = _load_mapping()
    for entry in mapping.get("alignments", []):
        axes = entry.get("axes", {})
        if (
            axes.get("law_chaos") == aln.law_chaos
            and axes.get("good_evil") == aln.good_evil
        ):
            return entry
    return None


def strategy_mix_for_alignment(aln: AlignmentConfig) -> List[Dict[str, Any]]:
    """
    Return a normalized game-theory strategy mix for this alignment.

    Example element:
      { "strategy": "Copycat", "weight": 0.4 }
    """
    entry = lookup_alignment_entry(aln)
    if entry is None:
        # Fallback: pure Copycat if alignment not found.
        return [{"strategy": "Copycat", "weight": 1.0}]

    mix = entry.get("strategy_mix", [])
    return _normalize_weights(mix, key="weight")


def _class_entry_for(dnd_class: str) -> Optional[Dict[str, Any]]:
    mapping = _load_mapping()
    dc = dnd_class.lower()
    for entry in mapping.get("classes", []):
        if entry.get("dnd_class", "").lower() == dc:
            return entry
    return None


def suggest_alignment_for_class(
    dnd_class: str,
    prefer_good: bool = True,
    fallback_alignment: Optional[AlignmentConfig] = None,
) -> AlignmentConfig:
    """
    Suggest an alignment for a given D&D class, using mapping hints.

    - If the class has favored_alignments in the JSON, we choose randomly among them.
    - If prefer_good=True, we bias toward *Good* labels when possible.
    - If nothing matches, fall back to the provided fallback_alignment or True Neutral.
    """
    class_entry = _class_entry_for(dnd_class)
    mapping = _load_mapping()

    def to_axes(label: str) -> Optional[Dict[str, str]]:
        for a in mapping.get("alignments", []):
            if a.get("label") == label:
                axes = a.get("axes", {})
                return {
                    "law_chaos": axes.get("law_chaos", "NEUTRAL"),
                    "good_evil": axes.get("good_evil", "NEUTRAL"),
                }
        return None

    candidates: List[str] = []

    if class_entry is not None:
        favored = class_entry.get("favored_alignments") or []
        if favored:
            candidates = list(favored)

    # Bias toward good if requested and there is a mix
    if candidates and prefer_good:
        goodish = [c for c in candidates if "Good" in c]
        if goodish:
            candidates = goodish

    # If we still have candidates, pick one and map to axes.
    if candidates:
        choice = random.choice(candidates)
        axes = to_axes(choice)
        if axes is not None:
            return AlignmentConfig(
                law_chaos=axes["law_chaos"],
                good_evil=axes["good_evil"],
                label=choice,
                default_strategy="Copycat",  # strategy can be refined via strategy_mix_for_alignment
            )

    # Fallback: use provided alignment if available
    if fallback_alignment is not None:
        return fallback_alignment

    # Final fallback: True Neutral
    tn_axes = to_axes("True Neutral")
    if tn_axes is None:
        # If the mapping is broken, at least give a valid AlignmentConfig
        return AlignmentConfig(
            law_chaos="NEUTRAL",
            good_evil="NEUTRAL",
            label="True Neutral",
            default_strategy="Random",
        )
    return AlignmentConfig(
        law_chaos=tn_axes["law_chaos"],
        good_evil=tn_axes["good_evil"],
        label="True Neutral",
        default_strategy="Random",
    )


# ---------------------------------------------------------------------------
# Demo / smoke test
# ---------------------------------------------------------------------------


def _demo() -> None:
    """
    Quick demo: show strategy mixes for Paladin & Puck, and a class suggestion.
    """
    # Paladin (Lawful Good)
    pal_aln = AlignmentConfig(
        law_chaos="LAWFUL",
        good_evil="GOOD",
        label="Lawful Good",
        default_strategy="Copykitten",
    )
    # Puck (Chaotic Neutral)
    puck_aln = AlignmentConfig(
        law_chaos="CHAOTIC",
        good_evil="NEUTRAL",
        label="Chaotic Neutral",
        default_strategy="Random",
    )

    pal_mix = strategy_mix_for_alignment(pal_aln)
    puck_mix = strategy_mix_for_alignment(puck_aln)

    pal_suggest = suggest_alignment_for_class("paladin")
    rogue_suggest = suggest_alignment_for_class("rogue")
    bard_suggest = suggest_alignment_for_class("bard")

    out = {
        "paladin_alignment": asdict(pal_aln),
        "paladin_strategy_mix": pal_mix,
        "puck_alignment": asdict(puck_aln),
        "puck_strategy_mix": puck_mix,
        "suggested_alignments": {
            "paladin": asdict(pal_suggest),
            "rogue": asdict(rogue_suggest),
            "bard": asdict(bard_suggest)
        }
    }

    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _demo()

