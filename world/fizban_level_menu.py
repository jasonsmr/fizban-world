#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_level_menu.py

Level-up "tarot spread" for agents:

- load_all_trees() -> dict[tree_id, LevelUpTree]
- eligible_nodes_across_trees(agent, trees) -> list[dict]
- build_tarot_spread(agent, trees, num_cards=3) -> list[dict]

Each spread card is:
{
  "tree_id": ...,
  "node_id": ...,
  "name": ...,
  "patron": ...,
  "cost_points": ...,
  "favor_for_patron": 0.0-1.0,
  "tags": [...],
  "short_hint": "why this card is showing up"
}
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Any

import json

from fizban_gods import compute_favor_for_agent
from fizban_level_tree import (
    LevelUpTree,
    LevelUpNode,
    load_level_tree,
    eligible_nodes_for_agent,
)


# ---------- Tree loading ----------


def load_all_trees(base_dir: Path | None = None) -> Dict[str, LevelUpTree]:
    """
    Load all *.json trees under world/trees.
    """
    if base_dir is None:
        base_dir = Path(__file__).resolve().parent
    trees_dir = base_dir / "trees"

    trees: Dict[str, LevelUpTree] = {}
    for path in sorted(trees_dir.glob("*.json")):
        tree = load_level_tree(path)
        trees[tree.id] = tree
    return trees


def eligible_nodes_across_trees(
    agent: Dict[str, Any],
    trees: Dict[str, LevelUpTree],
) -> List[Dict[str, Any]]:
    """
    Return a list of {"tree_id", "node"} entries for all eligible nodes.
    """
    results: List[Dict[str, Any]] = []
    for tree_id, tree in trees.items():
        for node in eligible_nodes_for_agent(agent, tree):
            results.append({"tree_id": tree_id, "node": node})
    return results


# ---------- Tarot-style level menu ----------


def build_tarot_spread(
    agent: Dict[str, Any],
    trees: Dict[str, LevelUpTree],
    num_cards: int = 3,
) -> List[Dict[str, Any]]:
    """
    Build a 'tarot spread' of up to num_cards level-up options for this agent.

    Strategy:
    - Compute favor for the agent (per god) and attach it to agent["favor"].
    - For each eligible node, score = favor[patron] (if any), fallback 0.5.
    - Sort descending by score, then ascending by cost_points.
    - Pick the top N, trying to diversify patrons when possible.
    """
    # Make a shallow copy so we can mutate safely
    agent = dict(agent)
    favors = compute_favor_for_agent(agent)
    agent["favor"] = favors

    eligible = eligible_nodes_across_trees(agent, trees)

    if not eligible:
        return []

    # Attach scores
    scored: List[Dict[str, Any]] = []
    for entry in eligible:
        node: LevelUpNode = entry["node"]
        patron = node.patron or ""
        favor_for_patron = float(favors.get(patron, 0.5)) if patron else 0.5
        score = favor_for_patron
        scored.append(
            {
                "tree_id": entry["tree_id"],
                "node": node,
                "score": score,
                "favor_for_patron": favor_for_patron,
            }
        )

    # Sort: higher score first, cheaper cost first, stable by name
    scored.sort(key=lambda e: (-e["score"], e["node"].cost_points, e["node"].name))

    spread: List[Dict[str, Any]] = []
    used_patrons = set()

    for entry in scored:
        if len(spread) >= num_cards:
            break
        node: LevelUpNode = entry["node"]
        patron = node.patron or ""
        # Simple diversity: try not to repeat patrons until necessary
        if patron and patron in used_patrons and len(used_patrons) < num_cards:
            continue
        used_patrons.add(patron)

        spread.append(
            {
                "tree_id": entry["tree_id"],
                "node_id": node.id,
                "name": node.name,
                "patron": patron,
                "cost_points": node.cost_points,
                "favor_for_patron": entry["favor_for_patron"],
                "tags": node.tags,
                "short_hint": _make_hint(node, entry["favor_for_patron"]),
            }
        )

    # Fallback: if spread is still smaller than num_cards because of diversity rule,
    # fill with remaining highest-scoring nodes.
    if len(spread) < num_cards:
        for entry in scored:
            if len(spread) >= num_cards:
                break
            node: LevelUpNode = entry["node"]
            if any(c["node_id"] == node.id for c in spread):
                continue
            spread.append(
                {
                    "tree_id": entry["tree_id"],
                    "node_id": node.id,
                    "name": node.name,
                    "patron": node.patron or "",
                    "cost_points": node.cost_points,
                    "favor_for_patron": entry["favor_for_patron"],
                    "tags": node.tags,
                    "short_hint": _make_hint(node, entry["favor_for_patron"]),
                }
            )

    return spread


def _make_hint(node: LevelUpNode, favor: float) -> str:
    patron = node.patron or "Unknown"
    if favor >= 0.7:
        mood = "favors you strongly"
    elif favor >= 0.5:
        mood = "is watching you with interest"
    elif favor >= 0.3:
        mood = "is unsure but curious"
    else:
        mood = "barely acknowledges you"
    tags = ", ".join(node.tags) if node.tags else "their domain"
    return f"{patron} {mood}; taking this boon nudges your story toward {tags}."


# ---------- Demo: Paladin & Puck spreads ----------


def _load_agent_from_v2(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    name = data.get("name", path.stem)
    alignment = data.get("alignment", {})
    cls = data.get("class", {})
    tags = data.get("tags", [])
    fate_baseline = data.get(
        "fate_baseline",
        {"grace": 0.5, "bounce_back": 0.5, "mental_strain": 0.1, "weird_mode": False},
    )
    level = cls.get("level", data.get("level", 1))

    agent = {
        "name": name,
        "alignment": alignment,
        "class": cls,
        "tags": tags,
        "fate": {
            "grace": float(fate_baseline.get("grace", 0.5)),
            "bounce_back": float(fate_baseline.get("bounce_back", 0.5)),
            "mental_strain": float(fate_baseline.get("mental_strain", 0.1)),
            "weird_mode": bool(fate_baseline.get("weird_mode", False)),
        },
        "favor": {},
        "unlocks": {"level_nodes": []},
        "level": int(level),
    }

    # Pre-compute favor so other tools can see it if needed
    agent["favor"] = compute_favor_for_agent(agent)
    return agent


def _demo() -> int:
    base_dir = Path(__file__).resolve().parent
    examples_dir = base_dir / "examples"

    paladin_path = examples_dir / "agent_paladin_v2.json"
    puck_path = examples_dir / "agent_puck_v2.json"

    paladin = _load_agent_from_v2(paladin_path)
    puck = _load_agent_from_v2(puck_path)

    trees = load_all_trees(base_dir)

    paladin_spread = build_tarot_spread(paladin, trees, num_cards=3)
    puck_spread = build_tarot_spread(puck, trees, num_cards=3)

    result = {
        "paladin_spread": paladin_spread,
        "puck_spread": puck_spread,
    }

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_demo())

