#!/usr/bin/env python3
"""
fizban_level_menu.py

Tarot-style level-up menu driven by:
- level trees (Titania / Oberon / Bottom / Lovers)
- current gods' favor (if present on agents)
- god reaction "whispers" for each card

This module is intentionally defensive about world-builder function names:
it will look for a usable builder in fizban_world_enrich *or* fizban_world_state
instead of assuming a specific name.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fizban_world_state import build_world_state
world = build_world_state()
# These are stable across your repo
from fizban_level_tree import eligible_nodes_for_agent
from fizban_god_reactions import compute_god_reactions

World = Dict[str, Any]
Card = Dict[str, Any]


PATRON_BY_TREE: Dict[str, str] = {
    "TITANIA_CORE_TREE": "Titania",
    "OBERON_TRADE_TREE": "Oberon",
    "BOTTOM_MASQUERADE_TREE": "Bottom",
    "LOVERS_BOND_TREE": "Lovers",
}


# ---------- World builder discovery ----------


def _discover_world_builder() -> callable:
    """
    Try very hard to find a world-building function.

    Priority:
    1. fizban_world_enrich: build_world_enriched / build_enriched_world /
       build_world_with_favor / build_world
    2. fizban_world_state: build_world_state / build_world / build_world_final

    Returns a zero-arg callable that builds a world dict, or raises a
    descriptive RuntimeError if nothing is found.
    """
    # Try enriched module first (if present)
    try:
        import fizban_world_enrich as _we  # type: ignore[import]
    except ImportError:
        _we = None

    try:
        import fizban_world_state as _ws  # type: ignore[import]
    except ImportError:
        _ws = None

    # (module, candidate_names)
    candidates = []
    if _we is not None:
        candidates.append(
            (
                _we,
                [
                    "build_world_enriched",
                    "build_enriched_world",
                    "build_world_with_favor",
                    "build_world",
                ],
            )
        )
    if _ws is not None:
        candidates.append(
            (
                _ws,
                [
                    "build_world_state",
                    "build_world",
                    "build_world_final",
                ],
            )
        )

    for module, names in candidates:
        for name in names:
            if hasattr(module, name):
                fn = getattr(module, name)
                if callable(fn):
                    return fn

    raise RuntimeError(
        "No usable world builder found.\n"
        "Expected one of:\n"
        "  - fizban_world_enrich.build_world_enriched / build_enriched_world / "
        "build_world_with_favor / build_world\n"
        "  - fizban_world_state.build_world_state / build_world / build_world_final\n"
        "Please expose at least one of these."
    )


# Bind once at import time
_BUILD_WORLD = _discover_world_builder()


def build_world_with_favor() -> World:
    """
    Build the world using the discovered builder.

    If agents already have .favor attached, we use it.
    If not, level menu will still work but all favor will be treated as 0.0.
    """
    world = _BUILD_WORLD()
    return world


# ---------- Small helpers ----------


def _get_agent(world: World, agent_name: str) -> Dict[str, Any]:
    wf = world.get("world_final") or {}
    agents = wf.get("agents") or {}
    return agents.get(agent_name, {})


def _get_favor(world: World, agent_name: str) -> Dict[str, float]:
    """
    Extract favor map for an agent, if present.

    Returns a {patron -> float} dict, defaulting to 0.0 if nothing is found.
    """
    agent = _get_agent(world, agent_name)
    raw = agent.get("favor") or {}
    return {str(k): float(v) for k, v in raw.items()}


# ---------- Core: cards / spreads ----------


def build_level_menu_for_agent(world: World, agent_name: str) -> List[Card]:
    """
    Build a tarot-like spread of candidate level-up nodes for an agent.

    Uses:
    - eligible_nodes_for_agent(world, agent_name)
    - PATRON_BY_TREE mapping
    - current favor (if available) to sort & annotate
    """
    favor = _get_favor(world, agent_name)

    # Ask level-tree engine which nodes are eligible in general
    nodes = eligible_nodes_for_agent(world, agent_name)

    cards: List[Card] = []

    for node in nodes:
        tree_id = node.get("tree_id")
        if tree_id not in PATRON_BY_TREE:
            # only our four patron trees for this spread
            continue

        # Focus on tier-1 "entry" nodes for now
        tier = int(node.get("tier", 1))
        if tier != 1:
            continue

        patron = PATRON_BY_TREE[tree_id]
        patron_favor = float(favor.get(patron, 0.0))

        tags = list(node.get("tags") or [])
        if tags:
            short_hint = (
                f"{patron} is watching you with interest; taking this boon nudges your story "
                f"toward " + ", ".join(tags) + "."
            )
        else:
            short_hint = f"{patron} is watching you with interest."

        card: Card = {
            "tree_id": tree_id,
            "node_id": node.get("node_id"),
            "name": node.get("name"),
            "patron": patron,
            "cost_points": 1,
            "favor_for_patron": patron_favor,
            "tags": tags,
            "short_hint": short_hint,
        }
        cards.append(card)

    # Highest favor cards first, then stable by patron/name
    cards.sort(
        key=lambda c: (
            -float(c.get("favor_for_patron", 0.0)),
            c.get("patron", ""),
            c.get("name", ""),
        )
    )
    return cards


def attach_god_whispers(world: World, agent_name: str, cards: List[Card]) -> List[Card]:
    """
    Look at god reactions and add 0–2 'god_whispers' lines to each card.

    We:
    - compute_god_reactions(world, events=[])
    - pick top_lines that mention the agent_name
    - fall back to patron headline if nothing specific
    """
    reactions = compute_god_reactions(world, events=[])

    enriched: List[Card] = []

    for card in cards:
        patron = card.get("patron")
        reaction = reactions.get(patron) or {}
        lines = reaction.get("top_lines") or []
        headline = reaction.get("headline") or ""

        whispers: List[str] = []

        # Prefer lines that explicitly mention the agent
        for line in lines:
            if agent_name in line:
                whispers.append(line)

        # Fallback: generic headline if nothing agent-specific
        if not whispers and headline:
            whispers.append(headline)

        card_with_whispers = dict(card)
        if whispers:
            card_with_whispers["god_whispers"] = whispers[:2]
        enriched.append(card_with_whispers)

    return enriched


def main() -> None:
    """
    CLI demo:
    - Build world
    - Build level menu for Paladin & Puck
    - Attach god whispers
    - Dump JSON
    """
    world = build_world_with_favor()

    paladin_raw = build_level_menu_for_agent(world, "Paladin")
    puck_raw = build_level_menu_for_agent(world, "Puck")

    paladin_spread = attach_god_whispers(world, "Paladin", paladin_raw)
    puck_spread = attach_god_whispers(world, "Puck", puck_raw)

    payload = {
        "paladin_spread": paladin_spread,
        "puck_spread": puck_spread,
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

