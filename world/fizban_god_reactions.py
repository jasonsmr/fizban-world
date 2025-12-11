#!/usr/bin/env python3
"""
fizban_god_reactions.py

Tiny narrative engine:
- Inspect agents in a world (favor, bloodlines, items, traits)
- Summarize each god's mood and focus
- Produce short reaction blurbs and structured hooks

Input world shape (as from fizban_world_enrich.enrich_world):
{
  "world_final": {
    "agents": {
      "Paladin": { ... },
      "Puck": { ... },
      ...
    }
  }
}
"""

from __future__ import annotations

from typing import Dict, Any, List, Tuple


World = Dict[str, Any]
Agent = Dict[str, Any]


PATRONS = ["Titania", "Oberon", "Bottom", "King", "Queen", "Lovers"]


# --- helpers --------------------------------------------------------------


def _agents(world: World) -> Dict[str, Agent]:
    wf = world.get("world_final") or {}
    return wf.get("agents") or {}


def _favor_for(agent: Agent, patron: str) -> float:
    return float(agent.get("favor", {}).get(patron, 0.0))


def _traits(agent: Agent) -> List[str]:
    tags = agent.get("tags") or []
    if isinstance(tags, list):
        return tags
    return list(tags)


def _bloodlines(agent: Agent) -> Dict[str, Any]:
    return agent.get("bloodlines") or {}


def _sentient_items(agent: Agent) -> Dict[str, Any]:
    return agent.get("sentient_items") or {}


def _favor_band(score: float) -> str:
    if score >= 0.75:
        return "adoring"
    if score >= 0.6:
        return "pleased"
    if score >= 0.45:
        return "curious"
    if score >= 0.3:
        return "uneasy"
    if score > 0.0:
        return "displeased"
    return "indifferent"


def _short_band_phrase(band: str) -> str:
    mapping = {
        "adoring": "is delighted by",
        "pleased": "is pleased with",
        "curious": "watches with interest",
        "uneasy": "is uneasy about",
        "displeased": "is quietly displeased with",
        "indifferent": "barely notices",
    }
    return mapping.get(band, "watches with interest")


# --- reaction computation -------------------------------------------------


def _summarize_patron_for_agent(patron: str, name: str, agent: Agent) -> Dict[str, Any]:
    favor = _favor_for(agent, patron)
    band = _favor_band(favor)
    traits = set(_traits(agent))
    bloodlines = _bloodlines(agent)
    items = _sentient_items(agent)

    hooks: List[str] = []

    # Bloodline hooks
    if bloodlines:
        if "angelic" in bloodlines and patron in ("King", "Titania"):
            hooks.append("angelic_bloodline")
        if "infernal" in bloodlines and patron in ("Bottom", "Lovers", "Queen"):
            hooks.append("infernal_bloodline")
        if "forest" in bloodlines and patron in ("Titania", "Queen"):
            hooks.append("forest_bloodline")

    # Trait hooks
    if "trickster" in traits and patron in ("Bottom", "Lovers", "Queen"):
        hooks.append("trickster_interest")
    if "hero" in traits and patron in ("King", "Titania", "Oberon"):
        hooks.append("heroic_expectations")
    if "devout" in traits and patron in ("King", "Titania"):
        hooks.append("pious_expectations")
    if "has_sentient_item" in traits and patron in ("Titania", "Queen"):
        hooks.append("curious_about_item")

    # Sentient item hooks
    if items and patron in ("Titania", "Queen"):
        hooks.append("sentient_item_bond")

    # Compose a short line
    mood_phrase = _short_band_phrase(band)
    base_line = f"{patron} {mood_phrase} {name}"

    # Flavor based on hooks (simple, but extensible)
    if "angelic_bloodline" in hooks:
        base_line += ", sensing latent wings and radiant duty."
    elif "infernal_bloodline" in hooks:
        base_line += ", wary of bargains that cut too deep."
    elif "forest_bloodline" in hooks:
        base_line += ", feeling roots of old oaths stirring."
    elif "trickster_interest" in hooks:
        base_line += ", amused by their mischief."
    elif "heroic_expectations" in hooks:
        base_line += ", expecting them to stand tall when the story turns."
    elif "curious_about_item" in hooks or "sentient_item_bond" in hooks:
        base_line += ", listening to the whispers of their relic."

    return {
        "agent": name,
        "favor": favor,
        "band": band,
        "hooks": sorted(set(hooks)),
        "line": base_line,
    }


def compute_god_reactions(
    world: World,
    events: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """
    Compute reactions per patron.

    events: optional list of recent events, e.g.
      { "type": "LEVEL_UP", "agent": "Paladin", "node_id": "TITANIA_GRACE_SPARK" }

    Right now we only attach events as extra context, but later they can steer specific lines.
    """
    agents = _agents(world)
    reactions: Dict[str, Any] = {}

    for patron in PATRONS:
        per_agents: List[Dict[str, Any]] = []
        for name, agent in agents.items():
            per_agents.append(_summarize_patron_for_agent(patron, name, agent))

        # Sort so most emotionally-loaded stuff floats up
        per_agents_sorted = sorted(
            per_agents,
            key=lambda x: x["favor"],
            reverse=True,
        )

        top_lines = [entry["line"] for entry in per_agents_sorted[:3]]

        # Simple "headline" for the patron
        if not per_agents_sorted:
            headline = f"{patron} sleeps; the world is quiet."
        else:
            top_agent = per_agents_sorted[0]
            if top_agent["band"] in ("adoring", "pleased"):
                headline = f"{patron} smiles on {top_agent['agent']} tonight."
            elif top_agent["band"] in ("uneasy", "displeased"):
                headline = f"{patron} is troubled by {top_agent['agent']}'s path."
            else:
                headline = f"{patron} watches the mortals with mild curiosity."

        reactions[patron] = {
            "headline": headline,
            "by_agent": per_agents_sorted,
            "top_lines": top_lines,
            "events_seen": events or [],
        }

    return reactions

