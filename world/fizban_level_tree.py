#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_level_tree.py

Lightweight level-tree engine:

- LevelUpNode / LevelUpTree dataclasses
- load_level_tree(path) -> LevelUpTree
- eligible_nodes_for_agent(agent, tree) -> list[LevelUpNode]
- apply_levelup_node(world_state, agent_name, node) -> world_state

Effects supported (so far):
- "fate.grace_delta": float
- "fate.bounce_back_delta": float
- "fate.mental_strain_delta": float
- "fate.weird_mode_bias": float   (stored in fate['weird_bias'])
- "favor.<God>_delta": float
- "traits.add": [tag, ...]
- "class_levels.<class>_delta": int
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from pathlib import Path
import json


@dataclass
class LevelUpNode:
    id: str
    name: str
    description: str
    patron: Optional[str] = None
    category: str = "generic"
    tags: List[str] = field(default_factory=list)
    cost_points: int = 1
    requires: Dict[str, Any] = field(default_factory=dict)
    effects: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LevelUpTree:
    id: str
    name: str
    description: str
    patron: Optional[str] = None
    nodes: Dict[str, LevelUpNode] = field(default_factory=dict)
    root_nodes: List[str] = field(default_factory=list)


def load_level_tree(path: Path) -> LevelUpTree:
    raw = json.loads(path.read_text(encoding="utf-8"))
    nodes: Dict[str, LevelUpNode] = {}

    for node_data in raw.get("nodes", []):
        nid = node_data["id"]
        nodes[nid] = LevelUpNode(
            id=nid,
            name=node_data.get("name", nid),
            description=node_data.get("description", ""),
            patron=node_data.get("patron", raw.get("patron")),
            category=node_data.get("category", "generic"),
            tags=node_data.get("tags", []),
            cost_points=int(node_data.get("cost_points", 1)),
            requires=node_data.get("requires", {}),
            effects=node_data.get("effects", {}),
        )

    return LevelUpTree(
        id=raw["id"],
        name=raw.get("name", raw["id"]),
        description=raw.get("description", ""),
        patron=raw.get("patron"),
        nodes=nodes,
        root_nodes=raw.get("root_nodes", []),
    )


def _get_agent_level(agent: Dict[str, Any]) -> int:
    return int(agent.get("level", 1))


def _get_agent_alignment(agent: Dict[str, Any]) -> Dict[str, str]:
    return agent.get("alignment", {})


def _get_agent_favor(agent: Dict[str, Any]) -> Dict[str, float]:
    return agent.get("favor", {})


def _get_agent_unlocked_nodes(agent: Dict[str, Any]) -> List[str]:
    unlocks = agent.setdefault("unlocks", {})
    nodes = unlocks.setdefault("level_nodes", [])
    return nodes


def node_is_eligible(agent: Dict[str, Any], node: LevelUpNode) -> bool:
    """
    Check whether this agent can take this node right now.
    """
    unlocked = set(_get_agent_unlocked_nodes(agent))
    if node.id in unlocked:
        return False

    requires = node.requires or {}

    # Level gate
    lvl = _get_agent_level(agent)
    min_level = int(requires.get("min_level", 1))
    max_level = int(requires.get("max_level", 999))
    if lvl < min_level or lvl > max_level:
        return False

    # Alignment band gate
    band = requires.get("alignment_band")
    if band:
        align = _get_agent_alignment(agent)
        a_lc = align.get("law_chaos")
        a_ge = align.get("good_evil")

        req_lc = band.get("law_chaos", "ANY")
        req_ge = band.get("good_evil", "ANY")

        if req_lc != "ANY" and a_lc is not None and a_lc != req_lc:
            return False
        if req_ge != "ANY" and a_ge is not None and a_ge != req_ge:
            return False

    # Favor gate
    favor_req: Dict[str, float] = requires.get("favor", {})
    if favor_req:
        favors = _get_agent_favor(agent)
        for god, threshold in favor_req.items():
            if float(favors.get(god, 0.0)) < float(threshold):
                return False

    # Quest flags gate
    quest_flags = set(requires.get("quest_flags", []))
    if quest_flags:
        agent_flags = set(agent.get("quests_completed", []))
        if not quest_flags.issubset(agent_flags):
            return False

    # Node prerequisites
    prereq = set(requires.get("nodes", []))
    if prereq and not prereq.issubset(unlocked):
        return False

    return True


def eligible_nodes_for_agent(agent: Dict[str, Any], tree: LevelUpTree) -> List[LevelUpNode]:
    """
    All nodes this agent could legally take right now.
    """
    return [n for n in tree.nodes.values() if node_is_eligible(agent, n)]


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def apply_node_to_agent(agent: Dict[str, Any], node: LevelUpNode) -> None:
    """
    Mutates agent in-place, applying node.effects and registering unlock.
    """
    unlocks = _get_agent_unlocked_nodes(agent)
    if node.id not in unlocks:
        unlocks.append(node.id)

    effects = node.effects or {}

    # Fate effects
    fate = agent.setdefault("fate", {})
    if "fate.grace_delta" in effects:
        fate["grace"] = _clamp01(float(fate.get("grace", 0.5)) + float(effects["fate.grace_delta"]))
    if "fate.bounce_back_delta" in effects:
        fate["bounce_back"] = _clamp01(
            float(fate.get("bounce_back", 0.5)) + float(effects["fate.bounce_back_delta"])
        )
    if "fate.mental_strain_delta" in effects:
        fate["mental_strain"] = _clamp01(
            float(fate.get("mental_strain", 0.1)) + float(effects["fate.mental_strain_delta"])
        )
    if "fate.weird_mode_bias" in effects:
        # store as a soft bias used by your fate engine
        fate["weird_bias"] = float(fate.get("weird_bias", 0.0)) + float(effects["fate.weird_mode_bias"])

    # Favor effects: keys like "favor.Titania_delta": 0.1
    favor = agent.setdefault("favor", {})
    for key, val in effects.items():
        if key.startswith("favor.") and key.endswith("_delta"):
            god_name = key[len("favor.") : -len("_delta")]
            favor[god_name] = _clamp01(float(favor.get(god_name, 0.0)) + float(val))

    # Traits / tags
    if "traits.add" in effects:
        add_tags = effects["traits.add"] or []
        tags = agent.setdefault("tags", [])
        for tag in add_tags:
            if tag not in tags:
                tags.append(tag)

    # Class level nudges: "class_levels.paladin_delta": 1
    class_levels = agent.setdefault("class_levels", {})
    for key, val in effects.items():
        if key.startswith("class_levels.") and key.endswith("_delta"):
            class_name = key[len("class_levels.") : -len("_delta")]
            class_levels[class_name] = int(class_levels.get(class_name, 0)) + int(val)


def apply_levelup_node(world_state: Dict[str, Any], agent_name: str, node: LevelUpNode) -> Dict[str, Any]:
    """
    Convenience wrapper: fetch agent by name and apply node.
    """
    agents = world_state.setdefault("agents", {})
    agent = agents.get(agent_name)
    if not agent:
        raise KeyError(f"Agent '{agent_name}' not found in world_state['agents']")
    apply_node_to_agent(agent, node)
    return world_state

