#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_traits.py

Derive high-level "traits" for an agent from:
- base tags
- class / level
- favor with gods
- unlocked level tree nodes

These traits are then used by:
- behavior engine (fizban_behavior)
- future: sentient items, curse logic, domain effects, etc.
"""

from __future__ import annotations

from typing import Dict, Any, List, Set

from fizban_gods import compute_favor_for_agent


def _class_traits(agent: Dict[str, Any]) -> Set[str]:
    traits: Set[str] = set()
    cls = (agent.get("class") or {}).get("dnd_class")

    if not cls:
        return traits

    cls = str(cls).lower()

    if cls == "paladin":
        traits.add("class_paladin")
        traits.add("divine_knight")
    elif cls == "rogue":
        traits.add("class_rogue")
        traits.add("trickster_heart")
    elif cls in ("cleric", "priest"):
        traits.add("class_cleric")
        traits.add("divine_channel")
    elif cls in ("druid", "forest_druid"):
        traits.add("class_druid")
        traits.add("forest_bloodline")
    elif cls in ("warlock", "sorcerer"):
        traits.add("class_warlock")
        traits.add("pact_bound")
    elif cls in ("wizard", "mage"):
        traits.add("class_wizard")
        traits.add("arcane_mind")
    elif cls in ("barbarian", "berserker"):
        traits.add("class_barbarian")
        traits.add("rage_bloodline")
    elif cls in ("monk", "battle_monk"):
        traits.add("class_monk")
        traits.add("chi_disciple")
    elif cls in ("bard",):
        traits.add("class_bard")
        traits.add("story_weaver")

    return traits


def _tree_traits(agent: Dict[str, Any]) -> Set[str]:
    """
    Map known level-tree node_ids to coarse-grained traits.
    Keeps this human-readable and easy to extend.
    """
    traits: Set[str] = set()
    unlocks = agent.get("unlocks") or {}
    level_nodes: List[str] = unlocks.get("level_nodes") or []

    node_set = set(level_nodes)

    # Titania core tree
    if "TITANIA_GRACE_SPARK" in node_set:
        traits.add("titania_sparked")
        traits.add("forest_guardian")

    if "TITANIA_WEIRD_BLOOM" in node_set:
        traits.add("weird_walks_with_fey")

    # Paladin oath tree
    if "PALADIN_OATH_INITIATE" in node_set:
        traits.add("oathbound")
        traits.add("vow_keeper")

    if "PALADIN_OATH_FOREST_SENTINEL" in node_set:
        traits.add("forest_sentinel")

    # Oberon trade tree
    if "OBERON_MERCHANT_MARK" in node_set:
        traits.add("merchant_marked")
        traits.add("trade_blessed")

    # Bottom masquerade tree
    if "BOTTOM_TRICKSTERS_MARK" in node_set:
        traits.add("bottom_favored")
        traits.add("mask_trickster")

    # Lovers bond tree
    if "LOVERS_FIRST_BOND" in node_set:
        traits.add("lover_bonded")
        traits.add("heart_marked")

    return traits


def _favor_traits(favor: Dict[str, float]) -> Set[str]:
    traits: Set[str] = set()

    t = float(favor.get("Titania", 0.0))
    o = float(favor.get("Oberon", 0.0))
    b = float(favor.get("Bottom", 0.0))
    k = float(favor.get("King", 0.0))
    q = float(favor.get("Queen", 0.0))
    l = float(favor.get("Lovers", 0.0))

    # Titania: forest, weirdness, fate
    if t >= 0.7:
        traits.add("titania_chosen")
    elif t >= 0.4:
        traits.add("titania_favored")

    # Oberon: order, trade, contracts
    if o >= 0.7:
        traits.add("oberon_chosen")
        traits.add("contracts_first")
    elif o >= 0.4:
        traits.add("oberon_favored")

    # Bottom: weird, chaos, theater
    if b >= 0.7:
        traits.add("bottom_chosen")
        traits.add("embraces_chaos")
    elif b >= 0.4:
        traits.add("bottom_favored")

    # King: stable rule, no raw evil
    if k >= 0.7:
        traits.add("king_chosen")
    elif k >= 0.4:
        traits.add("king_favored")

    # Queen: weird research, spy network
    if q >= 0.7:
        traits.add("queen_chosen")
        traits.add("spy_network_friend")
    elif q >= 0.4:
        traits.add("queen_favored")

    # Lovers: romance, bonds, social risk
    if l >= 0.7:
        traits.add("lovers_chosen")
    elif l >= 0.4:
        traits.add("lovers_favored")

    return traits


def derive_traits_for_agent(agent: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main public entrypoint.

    Returns:
    {
      "name": "...",
      "class": "...",
      "level": 3,
      "favor": {...},
      "traits": ["...","..."],
      "sources": {
        "base_tags": [...],
        "class_traits": [...],
        "tree_traits": [...],
        "favor_traits": [...]
      }
    }
    """
    base_tags = set(agent.get("tags") or [])
    class_tr = _class_traits(agent)

    favor = compute_favor_for_agent(agent)
    favor_tr = _favor_traits(favor)

    tree_tr = _tree_traits(agent)

    all_traits = base_tags | class_tr | favor_tr | tree_tr

    cls = (agent.get("class") or {}).get("dnd_class")
    lvl = (agent.get("class") or {}).get("level")

    return {
        "name": agent.get("name"),
        "class": cls,
        "level": lvl,
        "favor": favor,
        "traits": sorted(all_traits),
        "sources": {
            "base_tags": sorted(base_tags),
            "class_traits": sorted(class_tr),
            "tree_traits": sorted(tree_tr),
            "favor_traits": sorted(favor_tr),
        },
    }

