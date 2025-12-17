#!/usr/bin/env python3
"""
fizban_session_recap.py

Session recap helper:
- Compare world_before vs world_after
- Highlight interesting changes (levels, favor, bloodlines, sentient items, fate)
- Produce short recap lines + machine-friendly diff
"""

from __future__ import annotations

from typing import Dict, Any, List, Tuple

from fizban_god_reactions import compute_god_reactions

World = Dict[str, Any]
Agent = Dict[str, Any]


def _agents(world: World) -> Dict[str, Agent]:
    wf = world.get("world_final") or {}
    return wf.get("agents") or {}


def _get_fate(agent: Agent) -> Dict[str, float]:
    return agent.get("fate") or {}


def _get_level(agent: Agent) -> int:
    level = agent.get("level")
    if isinstance(level, (int, float)):
        return int(level)
    return int(agent.get("class", {}).get("level", 0))


def _get_favor(agent: Agent) -> Dict[str, float]:
    raw = agent.get("favor") or {}
    return {k: float(v) for k, v in raw.items()}


def _get_bloodline_state(agent: Agent) -> Dict[str, Any]:
    # From enrich_world: { id -> { "bloodline": {...}, "active_tiers": [...], ... } }
    return agent.get("bloodlines") or {}


def _get_items_state(agent: Agent) -> Dict[str, Any]:
    # From enrich_world: { item_id -> { "item": {...}, "abilities_granted": [...] } }
    return agent.get("sentient_items") or {}


def _summarize_agent_diff(
    name: str,
    before: Agent | None,
    after: Agent | None,
    favor_threshold: float = 0.05,
) -> Dict[str, Any]:
    """
    Return a structured diff for one agent.
    """
    if before is None and after is None:
        return {}

    diff: Dict[str, Any] = {"agent": name}

    if before is None:
        diff["status"] = "joined"
        return diff

    if after is None:
        diff["status"] = "left"
        return diff

    diff["status"] = "present"

    # Level
    lvl_before = _get_level(before)
    lvl_after = _get_level(after)
    lvl_delta = lvl_after - lvl_before
    if lvl_delta != 0:
        diff["level_change"] = {"before": lvl_before, "after": lvl_after, "delta": lvl_delta}

    # Fate
    fate_before = _get_fate(before)
    fate_after = _get_fate(after)
    fate_changes: Dict[str, Dict[str, float]] = {}
    for key in sorted(set(list(fate_before.keys()) + list(fate_after.keys()))):
        b = float(fate_before.get(key, 0.0))
        a = float(fate_after.get(key, 0.0))
        if abs(a - b) >= 0.01:
            fate_changes[key] = {"before": b, "after": a, "delta": a - b}
    if fate_changes:
        diff["fate_changes"] = fate_changes

    # Favor
    fav_before = _get_favor(before)
    fav_after = _get_favor(after)
    favor_changes: Dict[str, Dict[str, float]] = {}
    for patron in sorted(set(list(fav_before.keys()) + list(fav_after.keys()))):
        b = float(fav_before.get(patron, 0.0))
        a = float(fav_after.get(patron, 0.0))
        delta = a - b
        if abs(delta) >= favor_threshold:
            favor_changes[patron] = {"before": b, "after": a, "delta": delta}
    if favor_changes:
        diff["favor_changes"] = favor_changes

    # Bloodlines: track new active tiers
    bl_before = _get_bloodline_state(before)
    bl_after = _get_bloodline_state(after)
    new_bloodline_tiers: List[Tuple[str, str]] = []
    if bl_after:
        for bl_key, data in bl_after.items():
            after_tiers = {t["id"] for t in data.get("active_tiers") or []}
            before_tiers = set()
            if bl_key in bl_before:
                before_tiers = {t["id"] for t in bl_before[bl_key].get("active_tiers") or []}
            for tier_id in sorted(after_tiers - before_tiers):
                new_bloodline_tiers.append((bl_key, tier_id))
    if new_bloodline_tiers:
        diff["bloodline_tiers_unlocked"] = [
            {"bloodline_id": bl_id, "tier_id": tier_id}
            for (bl_id, tier_id) in new_bloodline_tiers
        ]

    # Sentient items: new item bonds
    items_before = _get_items_state(before)
    items_after = _get_items_state(after)
    new_items: List[str] = []
    bond_changes: Dict[str, Dict[str, float]] = {}
    for item_id, payload in items_after.items():
        if item_id not in items_before:
            new_items.append(item_id)
        before_item = items_before.get(item_id)
        after_item = payload
        before_bond = 0.0
        if before_item:
            before_bond = float(before_item.get("item", {}).get("bond_depth", 0.0))
        after_bond = float(after_item.get("item", {}).get("bond_depth", 0.0))
        if abs(after_bond - before_bond) >= 0.05:
            bond_changes[item_id] = {
                "before": before_bond,
                "after": after_bond,
                "delta": after_bond - before_bond,
            }

    if new_items:
        diff["new_sentient_items"] = new_items
    if bond_changes:
        diff["sentient_bond_changes"] = bond_changes

    return diff


def _headline_from_diffs(agent_diffs: Dict[str, Any]) -> List[str]:
    """
    Generate 2–5 compact recap lines.
    """
    lines: List[str] = []

    # Level-ups
    for name, diff in agent_diffs.items():
        lvl = diff.get("level_change")
        if lvl and lvl["delta"] > 0:
            lines.append(f"{name} advanced from level {lvl['before']} to {lvl['after']}.")

    # Bloodline unlocks
    for name, diff in agent_diffs.items():
        for bl in diff.get("bloodline_tiers_unlocked", []):
            bl_id = bl["bloodline_id"]
            tier_id = bl["tier_id"]
            lines.append(f"{name}'s {bl_id} bloodline unlocked tier {tier_id}.")

    # Sentient item bonds
    for name, diff in agent_diffs.items():
        bond_changes = diff.get("sentient_bond_changes") or {}
        for item_id, bc in bond_changes.items():
            if bc["delta"] > 0:
                lines.append(
                    f"{name}'s bond with {item_id} deepened (bond {bc['before']:.2f} → {bc['after']:.2f})."
                )

    # Favor swings
    for name, diff in agent_diffs.items():
        fav_changes = diff.get("favor_changes") or {}
        for patron, fc in fav_changes.items():
            direction = "grew" if fc["delta"] > 0 else "fell"
            lines.append(
                f"{patron}'s favor for {name} {direction} (Δ {fc['delta']:+.2f})."
            )

    # Cap length a bit
    if len(lines) > 5:
        return lines[:4] + ["...and more subtle shifts the gods are still weighing."]
    return lines


def compute_session_recap(
    world_before: World,
    world_after: World,
    events: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """
    High-level recap:
    - agent_diffs: per-agent structured changes
    - recap_lines: short narration bullets
    - gods_after: patron headlines after the changes
    """
    events = events or []

    before_agents = _agents(world_before)
    after_agents = _agents(world_after)

    agent_diffs: Dict[str, Any] = {}
    all_names = sorted(set(list(before_agents.keys()) + list(after_agents.keys())))

    for name in all_names:
        diff = _summarize_agent_diff(name, before_agents.get(name), after_agents.get(name))
        if diff:
            agent_diffs[name] = diff

    recap_lines = _headline_from_diffs(agent_diffs)

    # Optional: ask gods how they feel *after* the changes
    god_reactions = compute_god_reactions(world_after, events=events)
    god_headlines = {
        patron: data.get("headline", "")
        for patron, data in god_reactions.items()
    }

    return {
        "events": events,
        "agent_diffs": agent_diffs,
        "recap_lines": recap_lines,
        "god_headlines_after": god_headlines,
    }

