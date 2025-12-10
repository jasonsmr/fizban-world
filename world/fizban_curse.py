#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_curse.py

Curse / freeze system for level trees and boons.

Design goals:
- Never remove skills/boons; we only *block* new picks temporarily.
- Curses can:
    * Lock a patron (no new boons from that god).
    * Lock a specific tree (e.g. Oberon's trade tree).
    * Lock nodes with certain tags (e.g. "shadow_magic").
- Curses can be:
    * Pure cooldown-based (N rounds).
    * Location-based (only active in certain domains/temples).
    * Both (must be in location AND time not expired).

We treat "curse" broadly:
- God punishment.
- Domain limitation (holy ground).
- Future: powerful agents (e.g. succubus) applying seduction / confusion curses.

Curses are stored on agents as:

agent["curses"] = [
    {
        "id": "CURSE_OBERON_LOCK",
        "source": "Bottom",
        "type": "PATRON_LOCK",          # enum: PATRON_LOCK | TREE_LOCK | TAG_LOCK
        "target_patron": "Oberon",      # for PATRON_LOCK
        "duration_rounds": 10,          # optional
        "remaining_rounds": 7,          # optional
        "while_location_tags": ["trade_district"],  # optional
        "severity": 0.8                 # optional (0.0-1.0)
    },
    ...
]

This module does NOT mutate remaining_rounds automatically; use tick_curses()
from your world loop if you want per-round decay.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


Curse = Dict[str, Any]


# ---------- Core helpers ----------


def is_curse_active(
    curse: Curse,
    *,
    location_tags: Optional[List[str]] = None,
    round_index: Optional[int] = None,
) -> bool:
    """
    Return True if this curse is currently active given the context.

    Rules:
    - If while_location_tags is set, the agent must be in at least one of
      those tags for the curse to apply.
    - If remaining_rounds is present and <= 0, curse is inert.
    - If duration_rounds is set but remaining_rounds is missing, we treat
      it as "still active" unless your world loop decrements it.
    """
    location_tags = location_tags or []

    loc_required = curse.get("while_location_tags")
    if isinstance(loc_required, list) and loc_required:
        if not any(tag in location_tags for tag in loc_required):
            return False

    # Time-based gating
    if "remaining_rounds" in curse:
        try:
            if float(curse.get("remaining_rounds", 0.0)) <= 0.0:
                return False
        except (TypeError, ValueError):
            # Bad data: fail open and treat as active
            pass

    # We don't enforce round_index here; world loop can if desired.
    return True


def curse_blocks_node(
    curse: Curse,
    *,
    tree_id: str,
    node_patron: str,
    node_tags: List[str],
) -> bool:
    """
    Given an active curse and a level-tree node context, decide if it blocks this node.

    Supported types:
    - PATRON_LOCK: blocks any node whose patron == target_patron.
    - TREE_LOCK:   blocks any node from target_tree_id.
    - TAG_LOCK:    blocks any node with intersecting tags.
    """
    ctype = str(curse.get("type", "")).upper().strip()

    # Patron lock
    if ctype == "PATRON_LOCK":
        target_patron = str(curse.get("target_patron", "")).strip()
        if target_patron and node_patron and node_patron == target_patron:
            return True

    # Tree lock
    if ctype == "TREE_LOCK":
        target_tree_id = str(curse.get("target_tree_id", "")).strip()
        if target_tree_id and tree_id == target_tree_id:
            return True

    # Tag lock
    if ctype == "TAG_LOCK":
        target_tags = curse.get("target_tags") or []
        if any(t in node_tags for t in target_tags):
            return True

    return False


def filter_blocked_nodes_for_agent(
    agent: Dict[str, Any],
    entries: List[Dict[str, Any]],
    *,
    location_tags: Optional[List[str]] = None,
    round_index: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Given a list of {"tree_id", "node"} entries (like eligible_nodes_across_trees),
    filter out any nodes that are blocked by active curses on this agent.

    This is where the "freeze" behavior happens: nodes don't disappear from the tree,
    they're just hidden from level-up choice while cursed.
    """
    curses: List[Curse] = list(agent.get("curses") or [])
    if not curses:
        return entries

    active_curses: List[Curse] = [
        c for c in curses if is_curse_active(c, location_tags=location_tags, round_index=round_index)
    ]
    if not active_curses:
        return entries

    filtered: List[Dict[str, Any]] = []
    for entry in entries:
        tree_id = str(entry.get("tree_id", ""))
        node = entry.get("node")
        if node is None:
            continue

        node_patron = getattr(node, "patron", None) or ""
        node_tags = getattr(node, "tags", None) or []

        blocked = False
        for c in active_curses:
            if curse_blocks_node(c, tree_id=tree_id, node_patron=node_patron, node_tags=node_tags):
                blocked = True
                break

        if not blocked:
            filtered.append(entry)

    return filtered


# ---------- Optional: ticking curses over time ----------


def tick_curses(
    curses: List[Curse],
    *,
    rounds: int = 1,
) -> List[Curse]:
    """
    Return a new list of curses with remaining_rounds decremented by `rounds`
    (if present). This does NOT remove expired curses; you can filter them
    afterward if you wish.

    Example world loop:
        agent["curses"] = tick_curses(agent.get("curses", []), rounds=1)
        agent["curses"] = [c for c in agent["curses"] if is_curse_active(c)]
    """
    if rounds <= 0:
        return list(curses)

    out: List[Curse] = []
    for c in curses:
        c2 = dict(c)
        if "remaining_rounds" in c2:
            try:
                c2["remaining_rounds"] = float(c2.get("remaining_rounds", 0.0)) - float(rounds)
            except (TypeError, ValueError):
                # ignore bad data
                pass
        out.append(c2)
    return out


def add_curse(agent: Dict[str, Any], curse: Curse) -> None:
    """
    Convenience: attach a curse to an agent in-place.
    """
    curses = list(agent.get("curses") or [])
    curses.append(curse)
    agent["curses"] = curses

