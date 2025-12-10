#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_alignment.py

Core world-state types for Fizban-World:

- D&D-style alignment (Law/Chaos, Good/Evil)
- Titania's Grace: fate/destiny & bounce-back
- TrustLink edges between agents (Ncase-inspired)
- AgentState: one actor in the world
- Utility functions for trust updates, gossip, and destiny rolls
- JSON (de)serialization helpers for saving/loading worlds
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Tuple, Any


# ---------- Alignment ----------


class LawChaos(Enum):
    LAWFUL = -1
    NEUTRAL = 0
    CHAOTIC = 1


class GoodEvil(Enum):
    GOOD = 1
    NEUTRAL = 0
    EVIL = -1


@dataclass
class Alignment:
    law_chaos: LawChaos
    good_evil: GoodEvil

    @property
    def vector(self) -> Tuple[int, int]:
        """Return numeric vector (law_chaos, good_evil)."""
        return (self.law_chaos.value, self.good_evil.value)

    @property
    def label(self) -> str:
        """Return a classic D&D alignment label."""
        lc = self.law_chaos
        ge = self.good_evil

        if lc == LawChaos.NEUTRAL and ge == GoodEvil.NEUTRAL:
            return "True Neutral"

        def lc_str() -> str:
            if lc == LawChaos.LAWFUL:
                return "Lawful"
            if lc == LawChaos.CHAOTIC:
                return "Chaotic"
            return "Neutral"

        def ge_str() -> str:
            if ge == GoodEvil.GOOD:
                return "Good"
            if ge == GoodEvil.EVIL:
                return "Evil"
            return "Neutral"

        return f"{lc_str()} {ge_str()}"

    @property
    def default_strategy(self) -> str:
        """
        Map alignment to a default Ncase-style strategy name.

        Strategies: Cooperator, Cheater, Copycat, Grudger, Copykitten,
                    Simpleton, Random, Detective
        """
        lc, ge = self.vector

        # Strong Good, tends to cooperate
        if ge == 1 and lc <= 0:
            # Neutral/Chaotic Good -> more forgiving
            return "Copykitten"
        if ge == 1 and lc < 0:
            # Lawful Good -> principled cooperator
            return "Cooperator"

        # Strong Evil, tends to defect
        if ge == -1 and lc >= 0:
            # Lawful Evil -> calculating
            return "Detective"
        if ge == -1 and lc > 0:
            # Chaotic Evil -> pure chaos
            return "Cheater"

        # Neutral Good / Neutral Evil / True Neutral
        if ge == 0 and lc == 0:
            return "Simpleton"
        if ge == 0 and lc > 0:
            return "Random"
        if ge == 0 and lc < 0:
            return "Grudger"

        # Fallback
        return "Random"


# ---------- Trust & Fate ----------


@dataclass
class TrustLink:
    """
    i's view of j.
    """
    affinity: float = 0.0       # -1..1: deep mistrust -> deep trust
    gossip_bias: float = 0.0    # -1..1: bad rumors -> good rumors
    awe: float = 0.0            # 0..1: Oberon-flavored fascination
    boredom: float = 0.0        # 0..1: Bottom-flavored ennui
    last_outcome: str = "none"  # "CC", "CD", "DC", "DD", or "none"

    def clamp(self) -> None:
        self.affinity = max(-1.0, min(1.0, self.affinity))
        self.gossip_bias = max(-1.0, min(1.0, self.gossip_bias))
        self.awe = max(0.0, min(1.0, self.awe))
        self.boredom = max(0.0, min(1.0, self.boredom))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "affinity": self.affinity,
            "gossip_bias": self.gossip_bias,
            "awe": self.awe,
            "boredom": self.boredom,
            "last_outcome": self.last_outcome,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "TrustLink":
        return TrustLink(
            affinity=float(data.get("affinity", 0.0)),
            gossip_bias=float(data.get("gossip_bias", 0.0)),
            awe=float(data.get("awe", 0.0)),
            boredom=float(data.get("boredom", 0.0)),
            last_outcome=str(data.get("last_outcome", "none")),
        )


@dataclass
class TitaniasGrace:
    """
    Fate/destiny & resilience.

    - grace: -1..1, curse -> boon
    - bounce_back: 0..1, higher = recovers faster from emotional hits
    - mental_strain: accumulates from stress; high = fragile, weird mode
    """
    grace: float = 0.0
    bounce_back: float = 0.5
    mental_strain: float = 0.0

    def clamp(self) -> None:
        self.grace = max(-1.0, min(1.0, self.grace))
        self.bounce_back = max(0.0, min(1.0, self.bounce_back))
        self.mental_strain = max(0.0, self.mental_strain)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "grace": self.grace,
            "bounce_back": self.bounce_back,
            "mental_strain": self.mental_strain,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "TitaniasGrace":
        return TitaniasGrace(
            grace=float(data.get("grace", 0.0)),
            bounce_back=float(data.get("bounce_back", 0.5)),
            mental_strain=float(data.get("mental_strain", 0.0)),
        )


# ---------- Agent State ----------


@dataclass
class AgentState:
    name: str
    alignment: Alignment
    dnd_class: str = "commoner"           # e.g. rogue, bard, paladin
    tags: List[str] = field(default_factory=list)

    # Graph of trust edges: key is other agent name
    trust: Dict[str, TrustLink] = field(default_factory=dict)

    # Fate/destiny engine
    fate: TitaniasGrace = field(default_factory=TitaniasGrace)

    # Puck-style emotion summary
    current_emotion: str = "calm"
    awe_level: float = 0.0
    boredom_level: float = 0.0

    def ensure_link(self, other: str) -> TrustLink:
        if other not in self.trust:
            self.trust[other] = TrustLink()
        return self.trust[other]

    @property
    def alignment_label(self) -> str:
        return self.alignment.label

    @property
    def default_strategy(self) -> str:
        return self.alignment.default_strategy

    # ----- (De)Serialization -----

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "alignment": {
                "law_chaos": self.alignment.law_chaos.name,
                "good_evil": self.alignment.good_evil.name,
                "label": self.alignment.label,
                "default_strategy": self.alignment.default_strategy,
            },
            "dnd_class": self.dnd_class,
            "tags": list(self.tags),
            "trust": {k: v.to_dict() for (k, v) in self.trust.items()},
            "fate": self.fate.to_dict(),
            "current_emotion": self.current_emotion,
            "awe_level": self.awe_level,
            "boredom_level": self.boredom_level,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AgentState":
        a = data.get("alignment", {})
        lc_name = a.get("law_chaos", "NEUTRAL")
        ge_name = a.get("good_evil", "NEUTRAL")
        alignment = Alignment(
            law_chaos=LawChaos[lc_name],
            good_evil=GoodEvil[ge_name],
        )
        fate = TitaniasGrace.from_dict(data.get("fate", {}))
        trust_data = data.get("trust", {})

        agent = AgentState(
            name=data.get("name", "unknown"),
            alignment=alignment,
            dnd_class=data.get("dnd_class", "commoner"),
            tags=list(data.get("tags", [])),
            fate=fate,
            current_emotion=data.get("current_emotion", "calm"),
            awe_level=float(data.get("awe_level", 0.0)),
            boredom_level=float(data.get("boredom_level", 0.0)),
        )

        for other, link_obj in trust_data.items():
            agent.trust[other] = TrustLink.from_dict(link_obj)

        return agent


# ---------- Trust / Gossip / Fate Updates ----------


def update_trust_after_round(
    link: TrustLink,
    encounter_result: str,
    learning_rate: float = 0.1,
) -> None:
    """
    Update a TrustLink in-place based on an iterated Prisoner's Dilemma round.

    encounter_result is from i's perspective:
      - "CC": i cooperated, j cooperated
      - "CD": i cooperated, j defected
      - "DC": i defected, j cooperated
      - "DD": i defected, j defected
    """
    link.last_outcome = encounter_result

    if encounter_result == "CC":
        # mutual cooperation: affinity up, awe up, boredom down
        link.affinity += learning_rate
        link.awe += learning_rate * 0.5
        link.boredom -= learning_rate * 0.2

    elif encounter_result == "CD":
        # i cooperated, j defected: trust crashes, awe down
        link.affinity -= learning_rate * 2.0
        link.awe -= learning_rate * 0.7

    elif encounter_result == "DC":
        # i defected, j cooperated: might slightly increase i's sense
        # that j is exploitable, but less dramatic than CD
        link.affinity += learning_rate * 0.5
        link.boredom -= learning_rate * 0.1

    elif encounter_result == "DD":
        # mutual defection: everyone more jaded
        link.affinity -= learning_rate * 0.5
        link.boredom += learning_rate * 0.3

    link.clamp()


def apply_gossip(
    listener: AgentState,
    target_name: str,
    rumor_strength: float,
    positive: bool,
    source_trust: float,
) -> None:
    """
    Listener hears a rumor about target. Strength scaled by how much they trust the speaker.

    - rumor_strength: 0..1
    - positive: True=good rumor, False=bad rumor
    - source_trust: how much listener trusts the speaker (-1..1)
    """
    link = listener.ensure_link(target_name)
    # Gossip effect scales with both rumor_strength and source_trust
    sign = 1.0 if positive else -1.0
    delta = rumor_strength * (0.5 + 0.5 * source_trust) * sign
    link.gossip_bias += delta
    # small nudge to affinity as well
    link.affinity += delta * 0.25
    link.clamp()


def tick_fate_after_event(
    agent: AgentState,
    event_type: str,
    intensity: float = 1.0,
) -> None:
    """
    Adjust Titania's Grace & mental strain based on event_type.

    event_type examples:
      - "betrayal"
      - "heroic_deed"
      - "near_death"
      - "rest"
      - "love_moment"
    """
    f = agent.fate

    if event_type == "heroic_deed":
        f.grace += 0.1 * intensity
        f.mental_strain += 0.05 * intensity

    elif event_type == "betrayal":
        f.grace -= 0.15 * intensity
        f.mental_strain += 0.2 * intensity

    elif event_type == "near_death":
        f.grace += 0.05 * intensity  # survived: fate smiled
        f.mental_strain += 0.3 * intensity

    elif event_type == "rest":
        f.mental_strain -= 0.25 * intensity

    elif event_type == "love_moment":
        f.grace += 0.15 * intensity
        f.mental_strain -= 0.05 * intensity

    # Bounce-back slowly improves grace over time if strain is low
    if f.mental_strain < 0.5:
        f.grace += f.bounce_back * 0.02 * intensity

    f.clamp()


def destiny_roll(
    agent: AgentState,
    base_dc: int = 10,
    advantage: bool = False,
    disadvantage: bool = False,
) -> Dict[str, Any]:
    """
    Simulate a D&D-style d20 fate roll influenced by Titania's Grace.

    - grace > 0 gives a bonus, grace < 0 gives a penalty.
    - high mental_strain can impose disadvantage or penalties.
    """
    f = agent.fate
    # grace maps roughly -1..1 to a modifier of about -4..+4
    grace_mod = int(round(f.grace * 4.0))

    # mental strain penalty: more strain = worse luck
    strain_pen = int(math.floor(f.mental_strain))
    # If strain is very high, enforce disadvantage
    if f.mental_strain > 3.0:
        disadvantage = True

    def roll_d20() -> int:
        return random.randint(1, 20)

    if advantage and not disadvantage:
        r1, r2 = roll_d20(), roll_d20()
        base_roll = max(r1, r2)
        roll_type = "advantage"
    elif disadvantage and not advantage:
        r1, r2 = roll_d20(), roll_d20()
        base_roll = min(r1, r2)
        roll_type = "disadvantage"
    else:
        base_roll = roll_d20()
        roll_type = "normal"

    total = base_roll + grace_mod - strain_pen
    success = total >= base_dc

    return {
        "agent": agent.name,
        "alignment": agent.alignment_label,
        "base_roll": base_roll,
        "grace_mod": grace_mod,
        "strain_penalty": strain_pen,
        "total": total,
        "dc": base_dc,
        "success": success,
        "roll_type": roll_type,
    }


# ---------- World Serialization ----------


def save_agents(path: Path, agents: List[AgentState]) -> None:
    data = [a.to_dict() for a in agents]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_agents(path: Path) -> List[AgentState]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        # allow a dict of agents keyed by name
        return [AgentState.from_dict(v) for v in raw.values()]
    return [AgentState.from_dict(a) for a in raw]


def save_series_jsonl(path: Path, records: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

