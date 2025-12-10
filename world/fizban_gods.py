#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_gods.py

God configs + favor computation from world_state.

- GODS: Titania, Oberon, Bottom, King, Queen, Lovers
- compute_favor_for_agent(agent) -> dict[str, float]
- compute_favor_for_world(world_state) -> world_state (mutates agents[].favor)

This is intentionally lightweight and heuristic. It uses:
- alignment (law_chaos, good_evil)
- tags
- fate (grace, mental_strain, weird_mode)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any
from pathlib import Path
import json
import math


@dataclass
class GodConfig:
    name: str
    alignment_tilt: Dict[str, str]  # {"law_chaos": "...", "good_evil": "..."}
    loves_tags: List[str] = field(default_factory=list)
    hates_tags: List[str] = field(default_factory=list)
    boon_trees: List[str] = field(default_factory=list)


GODS: Dict[str, GodConfig] = {
    "Titania": GodConfig(
        name="Titania",
        alignment_tilt={"law_chaos": "NEUTRAL", "good_evil": "GOOD"},
        loves_tags=["titania", "forest", "weird", "oracle", "lover", "fate"],
        hates_tags=["bored", "brutal"],
        boon_trees=["TITANIA_CORE_TREE"],
    ),
    "Oberon": GodConfig(
        name="Oberon",
        alignment_tilt={"law_chaos": "LAWFUL", "good_evil": "NEUTRAL"},
        loves_tags=["merchant", "trader", "lawful", "kingdom", "contract"],
        hates_tags=["cheater", "oathbreaker"],
        boon_trees=[],
    ),
    "Bottom": GodConfig(
        name="Bottom",
        alignment_tilt={"law_chaos": "CHAOTIC", "good_evil": "NEUTRAL"},
        loves_tags=["trickster", "chaotic", "prankster", "weird"],
        hates_tags=["boring", "rigid"],
        boon_trees=[],
    ),
    "King": GodConfig(
        name="King",
        alignment_tilt={"law_chaos": "LAWFUL", "good_evil": "GOOD"},
        loves_tags=["hero", "protector", "knight", "paladin"],
        hates_tags=["demon", "tyrant"],
        boon_trees=[],
    ),
    "Queen": GodConfig(
        name="Queen",
        alignment_tilt={"law_chaos": "NEUTRAL", "good_evil": "NEUTRAL"},
        loves_tags=["weird", "psionic", "researcher", "spy"],
        hates_tags=["extremist"],
        boon_trees=[],
    ),
    "Lovers": GodConfig(
        name="Lovers",
        alignment_tilt={"law_chaos": "ANY", "good_evil": "ANY"},
        loves_tags=["lover", "romantic", "seducer", "bonded"],
        hates_tags=["betrayer"],
        boon_trees=[],
    ),
}


def _alignment_coords(law_chaos: str, good_evil: str) -> tuple[float, float]:
    lc_map = {"LAWFUL": 1.0, "NEUTRAL": 0.0, "CHAOTIC": -1.0, "ANY": 0.0}
    ge_map = {"GOOD": 1.0, "NEUTRAL": 0.0, "EVIL": -1.0, "ANY": 0.0}
    return lc_map.get(law_chaos, 0.0), ge_map.get(good_evil, 0.0)


def _alignment_score(agent_align: Dict[str, str], god_align: Dict[str, str]) -> float:
    """
    Returns 0..1 where 1.0 is perfect alignment, 0.0 is opposite on both axes.
    """
    a_lc = agent_align.get("law_chaos", "NEUTRAL")
    a_ge = agent_align.get("good_evil", "NEUTRAL")
    g_lc = god_align.get("law_chaos", "ANY")
    g_ge = god_align.get("good_evil", "ANY")

    # If god is ANY on an axis, treat distance on that axis as 0
    ax, ay = _alignment_coords(a_lc, a_ge)
    gx, gy = _alignment_coords(g_lc, g_ge)
    dx = 0.0 if g_lc == "ANY" else (ax - gx)
    dy = 0.0 if g_ge == "ANY" else (ay - gy)

    dist = math.sqrt(dx * dx + dy * dy)
    max_dist = math.sqrt(8.0)  # worst-case (1,1) vs (-1,-1)
    score = 1.0 - (dist / max_dist)
    if score < 0.0:
        score = 0.0
    if score > 1.0:
        score = 1.0
    return score


def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def compute_favor_for_agent(agent: Dict[str, Any]) -> Dict[str, float]:
    """
    Compute favor for a single agent based on alignment, tags, and fate.
    """
    alignment = agent.get("alignment", {})
    tags = set(agent.get("tags", []))
    fate = agent.get("fate", {})
    grace = float(fate.get("grace", 0.5))
    mental_strain = float(fate.get("mental_strain", 0.1))
    weird_mode = bool(fate.get("weird_mode", False))

    favors: Dict[str, float] = {}

    for name, god in GODS.items():
        score = 0.5  # neutral baseline

        # Alignment influence
        if alignment:
            a_score = _alignment_score(alignment, god.alignment_tilt)
            # center around 0.5, weight ~0.3
            score += (a_score - 0.5) * 0.3

        # Tag influence
        for t in tags:
            if t in god.loves_tags:
                score += 0.03
            if t in god.hates_tags:
                score -= 0.03

        # Special god-specific seasoning
        a_lc = alignment.get("law_chaos", "NEUTRAL")
        a_ge = alignment.get("good_evil", "NEUTRAL")

        if name == "Titania":
            score += (grace - 0.5) * 0.3
            if weird_mode:
                score += 0.05
            if "weird" in tags:
                score += 0.03
            if mental_strain > 0.6:
                # She worries you’re burning out
                score -= 0.05

        elif name == "Oberon":
            if a_lc == "LAWFUL":
                score += 0.05
            if "merchant" in tags or "trader" in tags:
                score += 0.07

        elif name == "Bottom":
            if a_lc == "CHAOTIC":
                score += 0.05
            if "trickster" in tags or "prankster" in tags:
                score += 0.07

        elif name == "King":
            if a_ge == "GOOD":
                score += 0.05
            if "hero" in tags or "paladin" in tags:
                score += 0.05

        elif name == "Queen":
            if "weird" in tags or "psionic" in tags:
                score += 0.06

        elif name == "Lovers":
            if "lover" in tags or "romantic" in tags or "bonded" in tags:
                score += 0.06

        favors[name] = clamp01(score)

    return favors


def compute_favor_for_world(world_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Given a world_state with world_state['agents'][name] dicts,
    attach/refresh agent['favor'] for every agent.
    """
    agents = world_state.get("agents", {})
    for name, agent in agents.items():
        agent["favor"] = compute_favor_for_agent(agent)
    return world_state


# --- Demo: load Paladin/Puck v2 configs and print favor snapshots ---


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

    return {
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


def _demo():
    base_dir = Path(__file__).resolve().parent
    examples_dir = base_dir / "examples"

    paladin_path = examples_dir / "agent_paladin_v2.json"
    puck_path = examples_dir / "agent_puck_v2.json"

    paladin = _load_agent_from_v2(paladin_path)
    puck = _load_agent_from_v2(puck_path)

    world = {"agents": {"Paladin": paladin, "Puck": puck}}
    world = compute_favor_for_world(world)

    print(json.dumps(world, indent=2))


if __name__ == "__main__":
    _demo()

