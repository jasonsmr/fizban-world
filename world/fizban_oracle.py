#!/usr/bin/env python3
"""
fizban_oracle.py

Small “oracle spread” helper that ties together:
- world state
- enriched world (bloodlines, items)
- god reactions

and produces a set of oracle cards a DM or UI can show.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from fizban_world_state import build_world_state
from fizban_world_enrich import enrich_world
from fizban_god_reactions import compute_god_reactions


@dataclass
class OracleCard:
    patron: str
    headline: str
    lines: List[str]
    omen_tags: List[str]


def _make_omen_tags(headline: str, lines: List[str]) -> List[str]:
    """
    Very simple tag extractor from the reaction text.
    This is where we can later get fancy (LLM / pattern tables / DM overrides).
    """
    blob = (headline + " " + " ".join(lines)).lower()
    tags: List[str] = []

    keywords = [
        "forest",
        "trade",
        "love",
        "lovers",
        "betray",
        "betrayal",
        "bloodline",
        "angel",
        "demon",
        "weird",
        "dream",
        "curse",
        "war",
        "peace",
        "oath",
        "trickster",
    ]

    for key in keywords:
        if key in blob:
            tags.append(key)

    # Deduplicate while preserving order
    seen = set()
    result: List[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def build_oracle_spread(
    world_enriched: Dict[str, Any],
    *,
    focus_agent: Optional[str] = None,
    max_cards: int = 3,
) -> List[OracleCard]:
    """
    Build a small oracle spread from an already-enriched world.

    - world_enriched: output from enrich_world(...)
    - focus_agent: if set, we prioritize cards whose text mentions this agent
    """
    # fizban_god_reactions expects a full world (enriched, including favor/traits)
    reactions = compute_god_reactions(world_enriched)

    cards: List[OracleCard] = []
    for patron, payload in reactions.items():
        headline = payload.get("headline", "").strip()
        lines = payload.get("top_lines", []) or []
        omen_tags = _make_omen_tags(headline, lines)

        cards.append(
            OracleCard(
                patron=patron,
                headline=headline,
                lines=lines,
                omen_tags=omen_tags,
            )
        )

    # If we have a focus agent (e.g. "Paladin" or player's name),
    # prioritize patrons whose lines talk about that agent.
    if focus_agent:
        focus = focus_agent

        def score(card: OracleCard) -> int:
            txt = " ".join(card.lines)
            return txt.count(focus)

        cards.sort(key=score, reverse=True)
    else:
        # Stable sort by patron name for deterministic ordering
        cards.sort(key=lambda c: c.patron)

    return cards[:max_cards]


def build_default_oracle_payload(
    *,
    focus_agent: str = "Paladin",
    max_cards: int = 3,
) -> Dict[str, Any]:
    """
    Convenience function:
      - builds base world
      - enriches it
      - computes oracle spread
    Returns a JSON-safe dict.
    """
    world = build_world_state()
    world_enriched = enrich_world(world)

    spread = build_oracle_spread(
        world_enriched,
        focus_agent=focus_agent,
        max_cards=max_cards,
    )

    return {
        "world_final": world_enriched["world_final"],
        "oracle_spread": [asdict(card) for card in spread],
    }


if __name__ == "__main__":
    # CLI entry: print just the oracle_spread as pretty JSON
    import json
    import sys

    payload = build_default_oracle_payload()
    json.dump(payload["oracle_spread"], sys.stdout, indent=2)
    print()

