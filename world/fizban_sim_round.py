#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_sim_round.py

Single-round trust/emotion interaction between two Fizban agents.

Usage:
  python3 fizban_sim_round.py agent_a.json agent_b.json \
      --out-a agent_a_next.json \
      --out-b agent_b_next.json

Prints a JSON summary of the round to stdout.
"""

import argparse
import json
import random
from pathlib import Path
from typing import Dict, Tuple

from fizban_agent import AgentState

from typing import Dict, Tuple, Optional

# ----- Payoff & interest helpers -----


def payoff(a: str, b: str) -> Tuple[float, float]:
    """
    Prisoner's Dilemma style payoff:
      C,C -> (2, 2)
      C,D -> (-1, 3)
      D,C -> (3, -1)
      D,D -> (0, 0)
    """
    if a == "C" and b == "C":
        return 2.0, 2.0
    if a == "C" and b == "D":
        return -1.0, 3.0
    if a == "D" and b == "C":
        return 3.0, -1.0
    return 0.0, 0.0


def shared_interest_score(a: AgentState, b: AgentState) -> float:
    """
    Very simple shared-interest measure: overlap of tags.
    Later we can fold in guilds, factions, quests, etc.
    """
    set_a = set(a.tags)
    set_b = set(b.tags)
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    if union == 0:
        return 0.0
    return inter / union


# ----- Strategy & bias helpers -----


def base_action_from_strategy(agent: AgentState, other_id: str) -> str:
    """
    Baseline C/D decision from Ncase-style strategies.
    For now, we ignore full history and only use trust level + a few rules of thumb.
    """
    strat = agent.trust_strategy

    if strat == "cooperator":
        return "C"
    if strat == "cheater":
        return "D"

    t = agent.get_trust(other_id)

    if strat == "copycat":
        # First interaction: default to cooperation if no strong distrust
        return "C" if t >= -0.2 else "D"

    if strat == "copykitten":
        # Slightly more forgiving copycat: default C unless very negative
        return "C" if t > -0.4 else "D"

    if strat == "grudger":
        # If we dislike them at all, defect
        return "C" if t >= 0.0 else "D"

    if strat == "simpleton":
        # Random with slight cooperation tilt
        return "C" if random.random() < 0.6 else "D"

    if strat == "random":
        return "C" if random.random() < 0.5 else "D"

    # Fallback
    return "C"


def align_bias(a: AgentState, b: AgentState, shared_interest: float) -> float:
    """
    Small alignment / shared-interest bias for cooperation probability.

    - Good vs Good -> more cooperation
    - Good vs Evil -> less
    - Shared-interest pushes toward cooperation
    """
    bias = 0.0

    # moral axis
    if a.alignment.moral_axis == "good" and b.alignment.moral_axis == "good":
        bias += 0.1
    elif {a.alignment.moral_axis, b.alignment.moral_axis} == {"good", "evil"}:
        bias -= 0.1

    # shared interests
    bias += 0.2 * shared_interest

    # clamp to a sane range
    if bias > 0.3:
        bias = 0.3
    if bias < -0.3:
        bias = -0.3

    return bias


def relationship_coop_bias(agent: AgentState, other_id: str) -> float:
    """
    Extra push toward or away from cooperation based on relationship.

    - Allies / permanent followers / love interests with positive affinity:
      more likely to cooperate.
    - Rivals with negative affinity:
      less likely to cooperate.
    """
    rel = agent.relationships.get(other_id)
    if rel is None:
        return 0.0

    bias = 0.0

    if rel.tier in ("ally", "permanent_follower", "love_interest"):
        if rel.affinity > 0.0:
            bias += 0.2 * rel.affinity  # up to +0.2

    if rel.tier == "rival":
        if rel.affinity < 0.0:
            bias -= 0.2 * (-rel.affinity)  # up to -0.2

    if rel.romantic and rel.affinity > 0.5:
        bias += 0.1  # lovers get an extra push to cooperate

    if bias > 0.5:
        bias = 0.5
    if bias < -0.5:
        bias = -0.5
    return bias


def decide_action(agent: AgentState, other: AgentState, s_interest: float) -> str:
    """
    Combine trust strategy baseline + alignment + interests + relationship
    into a final C/D choice.
    """
    base = base_action_from_strategy(agent, other.id)
    t = agent.get_trust(other.id)
    # map trust [-1,1] -> [0,1]
    trust_p = 0.5 * (t + 1.0)

    # base cooperation probability from trust
    p_coop = trust_p

    # add alignment/interest bias
    p_coop += align_bias(agent, other, s_interest)

    # add relationship bias (ally/lover/rival)
    p_coop += relationship_coop_bias(agent, other.id)

    # clamp
    if p_coop < 0.0:
        p_coop = 0.0
    if p_coop > 1.0:
        p_coop = 1.0

    # turn p_coop into a deterministic decision that nudges baseline:
    # if strongly cooperative -> force C
    # if strongly uncooperative -> force D
    # else keep baseline
    if p_coop >= 0.7:
        return "C"
    if p_coop <= 0.3:
        return "D"
    return base


# ----- Core round function -----


def run_round(
    agent_a: AgentState,
    agent_b: AgentState,
    forced_action_a: Optional[str] = None,
    forced_action_b: Optional[str] = None,
) -> Tuple[Dict, AgentState, AgentState]:
    """
    Perform one interaction round and return:
      (summary_dict, updated_agent_a, updated_agent_b)

    forced_action_a / forced_action_b:
      - If "C" or "D", override the decision logic for that side.
      - If None, use normal strategy/relationship-based decision.
    """
    s_interest = shared_interest_score(agent_a, agent_b)

    # Decide actions (with optional override)
    if forced_action_a in ("C", "D"):
        action_a = forced_action_a
    else:
        action_a = decide_action(agent_a, agent_b, s_interest)

    if forced_action_b in ("C", "D"):
        action_b = forced_action_b
    else:
        action_b = decide_action(agent_b, agent_a, s_interest)

    payoff_a_raw, payoff_b_raw = payoff(action_a, action_b)

    # Map raw payoff -> emotional payoff (just a simple scaling for now)
    payoff_a_emotion = 0.25 * payoff_a_raw
    payoff_b_emotion = 0.25 * payoff_b_raw

    # Betrayal flags
    betrayal_a = (action_a == "C" and action_b == "D")
    betrayal_b = (action_b == "C" and action_a == "D")


    # Outcome for trust update: from the perspective of each agent
    # +1 = I feel this was cooperative for me, -1 = betrayal, 0 = neutral
    def outcome_for(me_action: str, other_action: str) -> float:
        if me_action == "C" and other_action == "C":
            return 1.0
        if me_action == "D" and other_action == "D":
            return 0.0
        if me_action == "C" and other_action == "D":
            return -1.0
        if me_action == "D" and other_action == "C":
            return 1.0
        return 0.0

    outcome_a = outcome_for(action_a, action_b)
    outcome_b = outcome_for(action_b, action_a)

    # Update trust
    agent_a.update_trust_after_interaction(agent_b.id, outcome_a)
    agent_b.update_trust_after_interaction(agent_a.id, outcome_b)

    # Emotional impact (relationship-aware)
    agent_a.apply_emotional_impact(payoff_a_emotion, betrayal_a, other_id=agent_b.id)
    agent_b.apply_emotional_impact(payoff_b_emotion, betrayal_b, other_id=agent_a.id)

    # Cooldown heuristic: betrayal or high strain may raise cooldown
    if betrayal_a or agent_a.emotion.strain > 0.5:
        agent_a.bounce_back.cooldown = max(agent_a.bounce_back.cooldown, 2)
    else:
        if agent_a.bounce_back.cooldown > 0:
            agent_a.bounce_back.cooldown -= 1

    if betrayal_b or agent_b.emotion.strain > 0.5:
        agent_b.bounce_back.cooldown = max(agent_b.bounce_back.cooldown, 2)
    else:
        if agent_b.bounce_back.cooldown > 0:
            agent_b.bounce_back.cooldown -= 1

    summary = {
        "a_id": agent_a.id,
        "b_id": agent_b.id,
        "action_a": action_a,
        "action_b": action_b,
        "payoff_a_raw": payoff_a_raw,
        "payoff_b_raw": payoff_b_raw,
        "payoff_a_emotion": payoff_a_emotion,
        "payoff_b_emotion": payoff_b_emotion,
        "betrayal_a": betrayal_a,
        "betrayal_b": betrayal_b,
        "shared_interest": s_interest,
        "trust_a_after": agent_a.get_trust(agent_b.id),
        "trust_b_after": agent_b.get_trust(agent_a.id),
        "emotion_a_valence": agent_a.emotion.valence,
        "emotion_b_valence": agent_b.emotion.valence,
        "strain_a": agent_a.emotion.strain,
        "strain_b": agent_b.emotion.strain,
        "cooldown_a": agent_a.bounce_back.cooldown,
        "cooldown_b": agent_b.bounce_back.cooldown,
        "weird_mode_a": agent_a.emotion.weird_mode,
        "weird_mode_b": agent_b.emotion.weird_mode,
    }

    return summary, agent_a, agent_b


# ----- CLI -----


def load_agent(path: Path) -> AgentState:
    data = json.loads(path.read_text(encoding="utf-8"))
    return AgentState.from_dict(data)


def save_agent(path: Path, agent: AgentState) -> None:
    path.write_text(agent.to_json(), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Run a single Fizban trust/emotion round.")
    ap.add_argument("agent_a", type=str, help="Path to agent A JSON")
    ap.add_argument("agent_b", type=str, help="Path to agent B JSON")
    ap.add_argument(
        "--out-a",
        type=str,
        default=None,
        help="Where to write updated agent A JSON",
    )
    ap.add_argument(
        "--out-b",
        type=str,
        default=None,
        help="Where to write updated agent B JSON",
    )
    args = ap.parse_args()

    path_a = Path(args.agent_a).expanduser().resolve()
    path_b = Path(args.agent_b).expanduser().resolve()

    agent_a = load_agent(path_a)
    agent_b = load_agent(path_b)

    summary, agent_a_next, agent_b_next = run_round(agent_a, agent_b)

    # Print summary to stdout
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    # Save updated agents if requested
    if args.out_a:
        save_agent(Path(args.out_a).expanduser().resolve(), agent_a_next)
    if args.out_b:
        save_agent(Path(args.out_b).expanduser().resolve(), agent_b_next)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

