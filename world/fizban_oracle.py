#!/usr/bin/env python3
"""
fizban_oracle.py

Tarot-style oracle spread builder for Fizban World.

Takes the *current* enriched world state (agents + favor + bloodlines +
sentient items + god reactions + level trees) and produces a structured
"fortune spread" for an agent.

This is intentionally:
- JSON-friendly
- model-friendly (narrative_prompt is meant to be fed to an LLM)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

World = Dict[str, Any]


# --------- World builder + helpers ---------

def _discover_world_builder() -> callable:
    """
    Try very hard to find a world-building function.

    Priority:
      1. fizban_world_enrich: build_world_enriched / build_enriched_world /
         build_world_with_favor / build_world
      2. fizban_world_state: build_world_state / build_world / build_world_final
    """
    try:
        import fizban_world_enrich as _we  # type: ignore[import]
    except ImportError:
        _we = None

    try:
        import fizban_world_state as _ws  # type: ignore[import]
    except ImportError:
        _ws = None

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
        "fizban_oracle: No usable world builder found.\n"
        "Expected one of:\n"
        "  - fizban_world_enrich.build_world_enriched / build_enriched_world / "
        "build_world_with_favor / build_world\n"
        "  - fizban_world_state.build_world_state / build_world / build_world_final\n"
        "Please expose at least one of these."
    )


_BUILD_WORLD = _discover_world_builder()


def build_world_for_oracle() -> World:
    """Small wrapper in case you ever want to patch this."""
    return _BUILD_WORLD()


def _get_agent(world: World, agent_name: str) -> Dict[str, Any]:
    wf = world.get("world_final") or {}
    agents = wf.get("agents") or {}
    return agents.get(agent_name, {})


def _get_favor(agent: Dict[str, Any]) -> Dict[str, float]:
    return agent.get("favor") or {}


def _get_traits(agent: Dict[str, Any]) -> List[str]:
    traits = agent.get("traits") or []
    # Some modules put traits under .meta or .unlocks – we can merge later if needed.
    return list(sorted(set(traits)))


def _get_bloodlines(agent: Dict[str, Any]) -> Dict[str, Any]:
    return agent.get("bloodlines") or {}


def _get_sentient_items(agent: Dict[str, Any]) -> Dict[str, Any]:
    return agent.get("sentient_items") or {}


def _get_god_headlines(world: World) -> Dict[str, str]:
    """
    Reuse the god_reactions machinery if available.

    If you later change god_reactions, this automatically tracks it.
    """
    try:
        from fizban_god_reactions import compute_god_reactions  # type: ignore[import]
    except ImportError:
        return {}

    wf = world.get("world_final") or {}
    agents = wf.get("agents") or {}

    reactions = compute_god_reactions(agents=agents, world=world)
    out: Dict[str, str] = {}
    for god, payload in reactions.items():
        headline = payload.get("headline") or ""
        if isinstance(headline, str):
            out[god] = headline
    return out


def _get_level_cards_for_agent(world: World, agent_name: str) -> List[Dict[str, Any]]:
    """
    Ask fizban_level_menu for this agent's cards, if that module is present.

    Returns a list of lightweight card dicts.
    """
    try:
        import fizban_level_menu as _lm  # type: ignore[import]
    except ImportError:
        return []

    # Ideally use its own builder to keep things consistent
    build_world = getattr(_lm, "build_world_with_favor", None)
    if callable(build_world):
        w = build_world()
    else:
        # fall back to our world
        w = world

    fn = getattr(_lm, "build_level_menu_for_agent", None)
    if not callable(fn):
        return []

    cards = fn(w, agent_name)
    # cards might be a dict with 'cards' field or a plain list; normalize
    if isinstance(cards, dict) and "cards" in cards:
        cards = cards["cards"]

    out: List[Dict[str, Any]] = []
    if isinstance(cards, list):
        for c in cards:
            if isinstance(c, dict):
                out.append(c)
    return out


# --------- Oracle dataclasses ---------

@dataclass
class OracleCard:
    slot: str           # e.g. "past_root", "present_crossroads", "future_pull"
    title: str
    subtitle: str
    world_tags: List[str]
    narrative_prompt: str


@dataclass
class OracleSpread:
    agent: str
    spread_type: str
    summary: str
    cards: List[OracleCard]
    debug: Dict[str, Any]


# --------- Core spread logic ---------

def build_oracle_spread(world: World, agent_name: str,
                        spread_type: str = "past_present_future") -> OracleSpread:
    agent = _get_agent(world, agent_name)
    if not agent:
        raise ValueError(f"Oracle: agent '{agent_name}' not found in world")

    name = agent.get("name", agent_name)
    traits = _get_traits(agent)
    favor = _get_favor(agent)
    bloodlines = _get_bloodlines(agent)
    items = _get_sentient_items(agent)
    headlines = _get_god_headlines(world)
    level_cards = _get_level_cards_for_agent(world, agent_name)

    # Helper: pick a "strongest god" right now
    top_god = None
    top_f = float("-inf")
    for god, val in favor.items():
        if isinstance(val, (int, float)) and val > top_f:
            top_f = val
            top_god = god

    # Helper: pick one prominent bloodline tier (if any)
    active_bloodline_label = None
    if isinstance(bloodlines, dict):
        for bl in bloodlines.values():
            if not isinstance(bl, dict):
                continue
            binfo = bl.get("bloodline") or {}
            lbl = binfo.get("label")
            active_tiers = bl.get("active_tiers") or []
            if active_tiers and lbl:
                active_bloodline_label = lbl
                break

    # Helper: pick one notable sentient item
    notable_item_name = None
    for item_id, payload in items.items():
        item = payload.get("item") if isinstance(payload, dict) else payload
        if not isinstance(item, dict):
            continue
        notable_item_name = item.get("name") or item_id
        break

    # Helper: pick a "most tempting" level card
    chosen_card_title = None
    chosen_card_tags: List[str] = []
    if level_cards:
        # naive choice: first card
        card0 = level_cards[0]
        chosen_card_title = card0.get("name") or card0.get("node_id")
        tags = card0.get("tags") or []
        if isinstance(tags, list):
            chosen_card_tags = [str(t) for t in tags]

    # Build cards per slot
    cards: List[OracleCard] = []

    # 1) Past / Root
    past_tags = list(traits)
    if active_bloodline_label:
        past_tags.append("bloodline:" + active_bloodline_label)
    if notable_item_name:
        past_tags.append("item:" + notable_item_name)

    past_title = "Root of Your Path"
    past_subtitle = f"{name}'s story is rooted in old vows and lingering bloodlines."
    past_prompt = (
        f"Describe {name}'s past as a mix of their key traits {traits}, "
        f"any awakened bloodlines (e.g. {active_bloodline_label}), and the early "
        f"whispers of any sentient items (e.g. {notable_item_name}). "
        "Focus on formative moments, early oaths, and the first hints that the gods "
        "were watching."
    )

    cards.append(
        OracleCard(
            slot="past_root",
            title=past_title,
            subtitle=past_subtitle,
            world_tags=past_tags,
            narrative_prompt=past_prompt,
        )
    )

    # 2) Present / Crossroads
    headline_snippets = []
    for god, h in headlines.items():
        if god in favor and isinstance(h, str):
            headline_snippets.append(f"{god}: {h}")
    headline_snippets = headline_snippets[:3]

    present_tags: List[str] = []
    for god, val in sorted(favor.items(), key=lambda kv: kv[1], reverse=True):
        present_tags.append(f"favor:{god}:{val:.2f}")

    present_title = "At the Crossroads"
    if top_god:
        present_subtitle = f"{name} stands where {top_god}'s gaze feels strongest."
    else:
        present_subtitle = f"{name} stands between many quiet, watching powers."

    present_prompt = (
        f"Describe {name}'s current situation as a crossroads between the gods, "
        f"with favor map {favor} and headlines {headline_snippets}. "
        "Highlight current tensions: which gods pull them toward order, chaos, "
        "love, trade, or mischief? Mention any bloodline stirrings or sentient "
        "item demands that complicate the moment."
    )

    cards.append(
        OracleCard(
            slot="present_crossroads",
            title=present_title,
            subtitle=present_subtitle,
            world_tags=present_tags,
            narrative_prompt=present_prompt,
        )
    )

    # 3) Future / Pull
    future_tags: List[str] = []
    if chosen_card_title:
        future_tags.append("level_card:" + chosen_card_title)
    future_tags.extend(chosen_card_tags)

    future_title = "Pull of the Near Future"
    future_subtitle = (
        f"The next step beckons as '{chosen_card_title}'." if chosen_card_title
        else "The next step is hidden, but the gods are whispering."
    )

    future_prompt = (
        f"Describe where {name} is being pulled in the near future. "
        f"If relevant, center the narrative around the boon '{chosen_card_title}' "
        f"with tags {chosen_card_tags}. Show how accepting or rejecting this "
        "path would affect their favor with the gods, deepen or strain their "
        "bloodlines, and change their relationship with any sentient items."
    )

    cards.append(
        OracleCard(
            slot="future_pull",
            title=future_title,
            subtitle=future_subtitle,
            world_tags=future_tags,
            narrative_prompt=future_prompt,
        )
    )

    # Summary string for quick UI / logs
    summary = (
        f"Oracle spread for {name}: rooted in traits {traits}, "
        f"watched by {top_god or 'many gods'}, "
        f"tempted by {chosen_card_title or 'uncertain boons'}."
    )

    debug: Dict[str, Any] = {
        "traits": traits,
        "favor": favor,
        "bloodlines": bloodlines,
        "sentient_items": items,
        "god_headlines": headlines,
        "level_cards_sample": level_cards[:3],
    }

    return OracleSpread(
        agent=name,
        spread_type=spread_type,
        summary=summary,
        cards=cards,
        debug=debug,
    )


# --------- CLI / demo helper ---------

def demo_oracle(agent_name: str = "Paladin") -> None:
    world = build_world_for_oracle()
    spread = build_oracle_spread(world, agent_name=agent_name)
    print(json.dumps(
        {
            "agent": spread.agent,
            "spread_type": spread.spread_type,
            "summary": spread.summary,
            "cards": [asdict(c) for c in spread.cards],
            "debug": spread.debug,
        },
        indent=2,
        sort_keys=False,
    ))


if __name__ == "__main__":
    demo_oracle("Paladin")

