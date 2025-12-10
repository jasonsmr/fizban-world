#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_world_state.py
---------------------

Glue layer that ties together:

- AgentConfig (alignment, class, tags, baselines)
- A lightweight trust engine per pair of agents
- Titania's Grace fate state (grace, bounce_back, mental_strain)
- Round-by-round world history

This is intentionally self-contained: it does *not* depend on the other
math demo modules so we don't accidentally create circular imports.
We can refactor later once the shapes are stable.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from fizban_agent_config import (
    AgentConfig,
    AlignmentConfig,
    FateBaseline,
    load_agent_config,
)


# ---------------------------------------------------------------------------
# Alignment helpers (numeric grid)
# ---------------------------------------------------------------------------


def alignment_to_coords(aln: AlignmentConfig) -> Tuple[int, int]:
    """Map LAWFUL/NEUTRAL/CHAOTIC × GOOD/NEUTRAL/EVIL to integer coords."""
    law_map = {"LAWFUL": 1, "NEUTRAL": 0, "CHAOTIC": -1}
    good_map = {"GOOD": 1, "NEUTRAL": 0, "EVIL": -1}
    return law_map[aln.law_chaos], good_map[aln.good_evil]


def alignment_compatibility(a: AlignmentConfig, b: AlignmentConfig) -> float:
    """
    Soft compatibility score in [0,1].

    1.0 = identical alignment, 0.0 = maximally opposed (Lawful Good vs Chaotic Evil).
    We use Euclidean distance on the 3×3 alignment grid and soften with a sqrt
    so moderate distances are still fairly compatible.
    """
    ax, ay = alignment_to_coords(a)
    bx, by = alignment_to_coords(b)

    dx = ax - bx
    dy = ay - by
    dist = math.sqrt(dx * dx + dy * dy)

    max_dist = math.sqrt((1 - (-1)) ** 2 + (1 - (-1)) ** 2)  # sqrt(8)
    norm = max(0.0, min(1.0, 1.0 - dist / max_dist))
    softened = math.sqrt(norm)
    return softened


# ---------------------------------------------------------------------------
# Trust & Fate runtime state
# ---------------------------------------------------------------------------


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


@dataclass
class TrustState:
    """Runtime trust state vs a specific other agent."""

    affinity: float = 0.0      # -1..+1, how much I "like" this agent
    gossip_bias: float = 0.0   # -1..+1,  media/gossip skew
    awe: float = 0.0           # 0..1   (positive complacence)
    boredom: float = 0.0       # 0..1   (negative complacence)
    betrayal_count: float = 0.0
    cooperation_streak: float = 0.0
    last_outcome: Optional[str] = None  # "CC", "CD", "DC", "DD"


@dataclass
class FateState:
    """Runtime Titania's Grace state for a single agent."""

    grace: float = 0.5
    bounce_back: float = 0.5
    mental_strain: float = 0.0
    weird_mode: bool = False

    @staticmethod
    def from_baseline(b: FateBaseline) -> "FateState":
        return FateState(
            grace=_clamp(b.grace),
            bounce_back=_clamp(bounce_back) if (bounce_back := b.bounce_back) is not None else 0.5,  # type: ignore
            mental_strain=_clamp(b.mental_strain),
            weird_mode=False,
        )


@dataclass
class AgentRuntime:
    """Everything we need at runtime for an agent inside the world."""

    config: AgentConfig
    alignment_coords: Tuple[int, int]
    fate: FateState
    trust: Dict[str, TrustState] = field(default_factory=dict)
    # emotional snapshot (could be expanded later)
    current_emotion: str = "calm"
    awe_level: float = 0.0
    boredom_level: float = 0.0


@dataclass
class WorldState:
    agents: Dict[str, AgentRuntime]
    history: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Trust & Fate update rules for one round
# ---------------------------------------------------------------------------


def _update_trust_for_outcome(
    trust: TrustState,
    outcome: str,
    compat: float,
) -> Dict[str, float]:
    """
    Update trust state given an outcome code (CC, CD, DC, DD)
    and alignment compatibility.

    This is a simplified, local version of the logic that also appears
    in fizban_trust_math.py, tuned for readability.
    """
    delta_affinity = 0.0
    delta_betrayal = 0.0
    delta_coop_streak = 0.0

    # baseline deltas
    if outcome == "CC":
        # mutual cooperation, more positive when alignments are compatible
        delta_affinity = 0.15 * (0.5 + 0.5 * compat)
        delta_coop_streak = 1.0
        trust.awe = _clamp(trust.awe + 0.05)
        trust.boredom = _clamp(trust.boredom - 0.02)
    elif outcome == "DD":
        # mutual defection, mistrust grows more with *low* compatibility
        delta_affinity = -0.1 * (0.5 + 0.5 * (1.0 - compat))
        delta_coop_streak = 0.0
        trust.boredom = _clamp(trust.boredom + 0.04)
        trust.awe = _clamp(trust.awe - 0.03)
    elif outcome == "CD":
        # I Cooperate, they Defect (from MY POV) -> I was betrayed
        delta_affinity = -0.3
        delta_betrayal = 1.0
        delta_coop_streak = 0.0
        trust.awe = _clamp(trust.awe - 0.05)
        trust.boredom = _clamp(trust.boredom + 0.02)
    elif outcome == "DC":
        # I Defect, they Cooperate (from MY POV) -> I exploited them
        delta_affinity = -0.05
        delta_betrayal = 0.0
        delta_coop_streak = 0.0
        trust.awe = _clamp(trust.awe + 0.02)
        trust.boredom = _clamp(trust.boredom + 0.01)
    else:
        raise ValueError(f"Unknown outcome code: {outcome}")

    trust.affinity = _clamp(trust.affinity + delta_affinity, -1.0, 1.0)
    trust.betrayal_count = max(0.0, trust.betrayal_count + delta_betrayal)
    if delta_coop_streak > 0:
        trust.cooperation_streak += delta_coop_streak
    else:
        trust.cooperation_streak = 0.0

    trust.last_outcome = outcome

    return {
        "delta_affinity": delta_affinity,
        "delta_betrayal": delta_betrayal,
        "delta_coop_streak": delta_coop_streak,
    }


def _update_fate_for_outcome(
    fate: FateState,
    trust: TrustState,
    outcome: str,
) -> Dict[str, float]:
    """
    Update Titania's Grace / weird-mode knobs based on outcome and current trust.
    """
    delta_grace = 0.0
    delta_strain = 0.0
    delta_bounce = 0.0

    # Awe vs boredom act as a local "complacence slider" for how fate
    # reacts to successes/failures.
    complacence = trust.awe - trust.boredom  # -1..+1

    if outcome == "CC":
        delta_grace = 0.05 + 0.02 * complacence
        delta_strain = -0.02
        delta_bounce = 0.01
    elif outcome == "DD":
        delta_grace = -0.03
        delta_strain = 0.04 + 0.02 * max(0.0, trust.betrayal_count)
        delta_bounce = -0.01
    elif outcome == "CD":
        # I was betrayed
        delta_grace = -0.05
        delta_strain = 0.1
        delta_bounce = -0.02
    elif outcome == "DC":
        # I betrayed them
        delta_grace = -0.02
        delta_strain = 0.03
        delta_bounce = 0.0
    else:
        raise ValueError(f"Unknown outcome code: {outcome}")

    fate.grace = _clamp(fate.grace + delta_grace)
    fate.mental_strain = _clamp(fate.mental_strain + delta_strain)
    fate.bounce_back = _clamp(fate.bounce_back + delta_bounce)

    # Weird mode threshold: high sustained strain.
    fate.weird_mode = fate.mental_strain > 0.7

    return {
        "delta_grace": delta_grace,
        "delta_mental_strain": delta_strain,
        "delta_bounce_back": delta_bounce,
    }


def _mirror_outcome(outcome: str) -> str:
    """
    Given an outcome from A's perspective, return the code from B's perspective.
    """
    if outcome in ("CC", "DD"):
        return outcome
    if outcome == "CD":
        return "DC"
    if outcome == "DC":
        return "CD"
    raise ValueError(f"Unknown outcome code: {outcome}")


# ---------------------------------------------------------------------------
# World construction & stepping
# ---------------------------------------------------------------------------


def init_world_from_configs(configs: List[AgentConfig]) -> WorldState:
    """Build a WorldState from a list of AgentConfig."""
    agents: Dict[str, AgentRuntime] = {}

    for cfg in configs:
        coords = alignment_to_coords(cfg.alignment)
        fate = FateState.from_baseline(cfg.fate_baseline)

        trust_map: Dict[str, TrustState] = {}
        for tb in cfg.trust_baselines:
            trust_map[tb.target] = TrustState(
                affinity=_clamp(tb.affinity, -1.0, 1.0),
                gossip_bias=_clamp(tb.gossip_bias, -1.0, 1.0),
                awe=_clamp(tb.awe),
                boredom=_clamp(tb.boredom),
                betrayal_count=max(0.0, tb.betrayal_count),
                cooperation_streak=max(0.0, tb.cooperation_streak),
            )

        agents[cfg.name] = AgentRuntime(
            config=cfg,
            alignment_coords=coords,
            fate=fate,
            trust=trust_map,
            current_emotion="calm",
            awe_level=0.0,
            boredom_level=0.0,
        )

    return WorldState(agents=agents)


def play_interaction(
    world: WorldState,
    actor_a: str,
    actor_b: str,
    outcome_pair: str,
) -> Dict[str, Any]:
    """
    Apply one Prisoner's-Dilemma-style interaction between actor_a and actor_b.

    outcome_pair is from actor_a's perspective:
      - "CC": both cooperate
      - "CD": a cooperates, b defects  (a sees betrayal)
      - "DC": a defects, b cooperates  (a exploits b)
      - "DD": both defect
    """
    if outcome_pair not in ("CC", "CD", "DC", "DD"):
        raise ValueError(f"Invalid outcome_pair: {outcome_pair}")

    a = world.agents[actor_a]
    b = world.agents[actor_b]

    # fetch or create trust states
    trust_a = a.trust.get(actor_b) or TrustState()
    trust_b = b.trust.get(actor_a) or TrustState()

    a.trust[actor_b] = trust_a
    b.trust[actor_a] = trust_b

    compat = alignment_compatibility(a.config.alignment, b.config.alignment)

    # outcome for each perspective
    outcome_a = outcome_pair
    outcome_b = _mirror_outcome(outcome_pair)

    # update trust
    deltas_a = _update_trust_for_outcome(trust_a, outcome_a, compat)
    deltas_b = _update_trust_for_outcome(trust_b, outcome_b, compat)

    # update fate
    fate_deltas_a = _update_fate_for_outcome(a.fate, trust_a, outcome_a)
    fate_deltas_b = _update_fate_for_outcome(b.fate, trust_b, outcome_b)

    # simple emotional snapshot
    a.awe_level = trust_a.awe
    a.boredom_level = trust_a.boredom
    b.awe_level = trust_b.awe
    b.boredom_level = trust_b.boredom

    # crude emotion label just for debugging
    a.current_emotion = "awe" if a.awe_level > 0.5 else "bored" if a.boredom_level > 0.5 else "calm"
    b.current_emotion = "awe" if b.awe_level > 0.5 else "bored" if b.boredom_level > 0.5 else "calm"

    round_index = len(world.history) + 1
    entry = {
        "round": round_index,
        "pair": f"{actor_a} vs {actor_b}",
        "compatibility": compat,
        "outcome_pair": outcome_pair,
        "actor_a": {
            "name": actor_a,
            "outcome": outcome_a,
            "trust": asdict(trust_a),
            "fate": asdict(a.fate),
            "trust_deltas": deltas_a,
            "fate_deltas": fate_deltas_a,
        },
        "actor_b": {
            "name": actor_b,
            "outcome": outcome_b,
            "trust": asdict(trust_b),
            "fate": asdict(b.fate),
            "trust_deltas": deltas_b,
            "fate_deltas": fate_deltas_b,
        },
    }

    world.history.append(entry)
    return entry


# ---------------------------------------------------------------------------
# Destiny rolls
# ---------------------------------------------------------------------------


def destiny_roll_for_agent(
    agent: AgentRuntime,
    dc: int = 12,
    advantage: bool = False,
    disadvantage: bool = False,
) -> Dict[str, Any]:
    """
    D20-style destiny roll biased by Titania's Grace and mental strain.

    - grace > 0.5 gives a positive modifier.
    - high mental_strain gives a penalty.
    - advantage/disadvantage work like D&D.
    """
    if advantage and disadvantage:
        advantage = False
        disadvantage = False

    def roll_d20() -> int:
        return random.randint(1, 20)

    r1 = roll_d20()
    base_roll = r1

    if advantage:
        r2 = roll_d20()
        base_roll = max(r1, r2)
    elif disadvantage:
        r2 = roll_d20()
        base_roll = min(r1, r2)

    grace_mod = int(round((agent.fate.grace - 0.5) * 4.0))
    strain_penalty = int(round(agent.fate.mental_strain * 4.0))

    total = base_roll + grace_mod - strain_penalty
    success = total >= dc

    return {
        "agent": agent.config.name,
        "alignment": agent.config.alignment.label,
        "base_roll": base_roll,
        "grace_mod": grace_mod,
        "strain_penalty": strain_penalty,
        "total": total,
        "dc": dc,
        "success": success,
        "roll_type": "advantage" if advantage else "disadvantage" if disadvantage else "normal",
        "fate_snapshot": asdict(agent.fate),
    }


def destiny_roll_for_pair(
    world: WorldState,
    actor_a: str,
    actor_b: str,
    dc: int = 12,
) -> Dict[str, Any]:
    """Convenience: roll destiny for both agents in a pair."""
    a = world.agents[actor_a]
    b = world.agents[actor_b]
    return {
        actor_a: destiny_roll_for_agent(a, dc=dc),
        actor_b: destiny_roll_for_agent(b, dc=dc),
    }


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def world_to_dict(world: WorldState) -> Dict[str, Any]:
    """Snapshot all agents into a JSON-serializable dict."""
    agents_out: Dict[str, Any] = {}
    for name, rt in world.agents.items():
        agents_out[name] = {
            "name": name,
            "alignment": {
                "law_chaos": rt.config.alignment.law_chaos,
                "good_evil": rt.config.alignment.good_evil,
                "label": rt.config.alignment.label,
                "default_strategy": rt.config.alignment.default_strategy,
                "coords": list(rt.alignment_coords),
            },
            "class": {
                "dnd_class": rt.config.klass.dnd_class,
                "level": rt.config.klass.level,
                "job_tags": rt.config.klass.job_tags,
            },
            "tags": rt.config.tags,
            "fate": asdict(rt.fate),
            "trust": {target: asdict(ts) for target, ts in rt.trust.items()},
            "current_emotion": rt.current_emotion,
            "awe_level": rt.awe_level,
            "boredom_level": rt.boredom_level,
        }
    return {
        "agents": agents_out,
    }


# ---------------------------------------------------------------------------
# Tiny self-test
# ---------------------------------------------------------------------------


def _demo() -> None:
    """Quick smoke test: load Paladin & Puck v2 and run a short script."""
    base = Path(__file__).resolve().parent
    examples = base / "examples"

    pal_cfg = load_agent_config(examples / "agent_paladin_v2.json")
    puck_cfg = load_agent_config(examples / "agent_puck_v2.json")

    world = init_world_from_configs([pal_cfg, puck_cfg])

    script = ["CC", "CC", "CC", "CD", "CC"]

    for oc in script:
        _ = play_interaction(world, "Paladin", "Puck", oc)

    destiny = destiny_roll_for_pair(world, "Paladin", "Puck", dc=12)

    out = {
        "world_final": world_to_dict(world),
        "history": world.history,
        "destiny": destiny,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _demo()

