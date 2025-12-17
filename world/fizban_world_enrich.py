#!/usr/bin/env python3
"""
fizban_world_enrich.py

Glue layer that:
- inspects agents (traits, favor, level, weirdness)
- attaches bloodline progress info
- attaches sentient items (e.g. forest heirloom) when appropriate
- applies item fate modifiers

Does NOT mutate other world modules; it just wraps and returns an enriched copy.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, Any, List

from fizban_bloodline import (
    evaluate_bloodline_progress,
    make_bloodline_angelic_scion,
    make_bloodline_demonic_infernal,
    make_bloodline_forest_heir_druidic,
)
from fizban_sentient_item import (
    apply_item_to_fate,
    granted_abilities_for_item,
    make_forest_ancestor_heirloom,
    tick_item_bond,
)


World = Dict[str, Any]
Agent = Dict[str, Any]


# --- small helpers --------------------------------------------------------


def _get_weird_level_from_fate(fate: Dict[str, Any]) -> float:
    """
    Fate has 'weird_mode' bool and maybe an implicit weirdness.
    For now: weird_mode=True => at least 0.2, else 0.1 baseline.
    """
    if not fate:
        return 0.0
    if fate.get("weird_mode", False):
        return 0.2
    # subtle weird baseline
    return 0.1


def _ensure_list_tags(agent: Agent) -> List[str]:
    tags = agent.get("tags") or []
    if isinstance(tags, list):
        return tags
    return list(tags)


def _agent_favor(agent: Agent) -> Dict[str, float]:
    return dict(agent.get("favor", {}))


def _agent_level(agent: Agent) -> int:
    # many of your agents already carry "level" on the top-level agent dict
    return int(agent.get("level") or agent.get("class", {}).get("level", 1))


# --- bloodline inference --------------------------------------------------


def infer_candidate_bloodlines(agent: Agent) -> Dict[str, Any]:
    """
    Decide which bloodlines are worth checking for this agent, based on tags/class.
    Returns a dict of id -> Bloodline instance.
    """
    tags = set(_ensure_list_tags(agent))
    dnd_class = (agent.get("class") or {}).get("dnd_class", "").lower()

    candidates = {}

    # Paladin / heroic -> angelic
    if "class_paladin" in tags or dnd_class == "paladin" or "hero" in tags:
        candidates["angelic"] = make_bloodline_angelic_scion()

    # Rogue / trickster / ambitious -> infernal
    if (
        "class_rogue" in tags
        or dnd_class == "rogue"
        or "trickster" in tags
        or "ambitious" in tags
    ):
        candidates["infernal"] = make_bloodline_demonic_infernal()

    # Forest child / druid -> forest heir
    if "forest_child" in tags or dnd_class == "druid":
        candidates["forest"] = make_bloodline_forest_heir_druidic()

    return candidates


def enrich_agent_bloodlines(agent: Agent) -> Agent:
    """
    Attach bloodline progression info under agent["bloodlines"].
    """
    agent = deepcopy(agent)
    level = _agent_level(agent)
    fate = agent.get("fate") or {}
    weird_level = _get_weird_level_from_fate(fate)
    favor = _agent_favor(agent)
    tags = _ensure_list_tags(agent)

    candidates = infer_candidate_bloodlines(agent)
    bloodlines_out: Dict[str, Any] = {}

    for key, bl in candidates.items():
        res = evaluate_bloodline_progress(
            bl,
            level=level,
            weird_level=weird_level,
            favor=favor,
            traits=tags,
        )
        # Only keep if at least one tier active
        if res["active_tiers"]:
            bloodlines_out[key] = res

    if bloodlines_out:
        agent["bloodlines"] = bloodlines_out

    return agent


# --- sentient item attachment ---------------------------------------------


def maybe_attach_forest_heirloom(agent: Agent) -> Agent:
    """
    If the agent looks like a forest heir, attach Heartroot Diadem and apply effects.
    """
    agent = deepcopy(agent)
    tags = set(_ensure_list_tags(agent))
    dnd_class = (agent.get("class") or {}).get("dnd_class", "").lower()

    # Heuristic: druid + forest_child or a forest bloodline => candidate
    has_forest_tag = "forest_child" in tags or "bloodline_forest_latent" in tags
    if not (has_forest_tag or dnd_class == "druid"):
        return agent

    level = _agent_level(agent)
    fate = agent.get("fate") or {}
    stats = agent.get("stats") or {
        "near_death_events": 1,
        "forest_rites_completed": 1,
    }

    item = make_forest_ancestor_heirloom()
    # Bond based on a rough “how dramatic has the story been” guess.
    item = tick_item_bond(
        item,
        agent_name=str(agent.get("name", "Unknown")),
        events={
            "quest_completed": float(stats.get("forest_rites_completed", 0)),
            "trauma": float(stats.get("near_death_events", 0)),
            "betrayed_item_values": False,
        },
    )

    abilities = granted_abilities_for_item(item, agent_level=level)
    fate_after = apply_item_to_fate(item, fate)

    agent.setdefault("sentient_items", {})
    agent["sentient_items"][item.id] = {
        "item": item.to_dict(),
        "abilities_granted": abilities,
    }
    agent["fate"] = fate_after

    # Also tag the agent so other systems know they’re bound
    tags.add("has_sentient_item")
    agent["tags"] = sorted(tags)

    return agent


# --- full world enrichment ------------------------------------------------


def enrich_agent(agent: Agent) -> Agent:
    """
    Pipeline for one agent:
      - bloodlines
      - sentient forest heirloom (if relevant)
    """
    out = enrich_agent_bloodlines(agent)
    out = maybe_attach_forest_heirloom(out)
    return out


def enrich_world(world: World) -> World:
    """
    Given a world with:
      { "world_final": { "agents": { "Paladin": {..}, "Puck": {..} } } }

    return a new world with enriched agents.
    """
    world = deepcopy(world)
    wf = world.get("world_final") or {}
    agents = wf.get("agents") or {}

    new_agents: Dict[str, Any] = {}
    for name, agent in agents.items():
        new_agents[name] = enrich_agent(agent)

    wf["agents"] = new_agents
    world["world_final"] = wf
    return world

