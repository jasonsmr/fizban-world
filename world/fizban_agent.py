#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_agent.py

Core data structures and simple math for a single Fizban agent:
- D&D-style alignment
- Ncase-style trust strategy + trust matrix
- Emotion (valence/arousal/stance + complacence + strain)
- Titania's Grace (class/job/boons)
- Bounce-back / resilience

This is *offline* simulation math: no API calls here.
We can later wrap this with a "brains" module that calls fizban-dev.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Literal, Optional


LawAxis = Literal["lawful", "neutral", "chaotic"]
MoralAxis = Literal["good", "neutral", "evil"]

TrustStrategy = Literal[
    "copycat",
    "copykitten",
    "cooperator",
    "cheater",
    "grudger",
    "detective",
    "simpleton",
    "random",
    "texan",
    "two_cat"
]


@dataclass
class Alignment:
    law_axis: LawAxis = "neutral"
    moral_axis: MoralAxis = "neutral"

    @property
    def label(self) -> str:
        return f"{self.law_axis}_{self.moral_axis}"


@dataclass
class Complacence:
    mode: Literal["neutral", "awe", "boredom"] = "neutral"
    level: float = 0.0  # 0..1


@dataclass
class EmotionState:
    valence: float = 0.0    # -1..1 (sad/angry -> happy/joyful)
    arousal: float = 0.0    # 0..1  (calm -> excited)
    stance: float = 0.0     # -1..1 (avoid/flight -> approach)
    complacence: Complacence = field(default_factory=Complacence)
    strain: float = 0.0     # 0..1 mental fatigue / weirdness
    weird_mode: bool = False


@dataclass
class Boon:
    name: str
    rank: int = 1


@dataclass
class TitaniasGrace:
    class_name: str = "commoner"  # 'class' is reserved word in Python
    job: str = "villager"
    level: int = 1
    alignment_shift_tendency: str = "stable"  # e.g. towards_good, towards_chaotic
    boons: List[Boon] = field(default_factory=list)
    fate_bias_toward_trust: float = 0.0   # small positive = nudged to trust
    fate_bias_toward_betrayal: float = 0.0  # small positive = nudged to betrayal

    def add_boon(self, name: str, rank: int = 1) -> None:
        self.boons.append(Boon(name=name, rank=rank))


@dataclass
class BounceBack:
    resilience: float = 0.5    # 0..1: higher = recovers faster
    resentment: float = 0.0    # 0..1: higher = holds grudges
    cooldown: int = 0          # ticks until "normal" again


# Relationship tiers between this agent and another specific agent.
RelationshipTier = Literal[
    "stranger",
    "acquaintance",
    "ally",
    "permanent_follower",
    "love_interest",
    "rival",
]


@dataclass
class RelationshipState:
    tier: RelationshipTier = "stranger"
    affinity: float = 0.0   # -1..1 (hate -> like/love)
    romantic: bool = False  # romantic flag; lover vs just ally


@dataclass
class Inventory:
    gold: int = 0
    items: List[str] = field(default_factory=list)


@dataclass
class AgentState:
    id: str
    name: str
    kind: str = "human"
    tags: List[str] = field(default_factory=list)

    alignment: Alignment = field(default_factory=Alignment)
    trust_strategy: TrustStrategy = "copycat"

    # trust in others: agent_id -> trust score -1..1
    trust_matrix: Dict[str, float] = field(default_factory=dict)

    # gossip: prior bias before first meeting
    gossip_bias: Dict[str, float] = field(default_factory=dict)

    emotion: EmotionState = field(default_factory=EmotionState)
    titanias_grace: TitaniasGrace = field(default_factory=TitaniasGrace)
    bounce_back: BounceBack = field(default_factory=BounceBack)
    inventory: Inventory = field(default_factory=Inventory)

    # per-other relationships: other_id -> RelationshipState
    relationships: Dict[str, RelationshipState] = field(default_factory=dict)

    # ----- serialization -----

    def to_dict(self) -> dict:
        def _conv(obj):
            if hasattr(obj, "__dict__") or isinstance(obj, (list, dict)):
                return asdict(obj)
            return obj

        return _conv(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AgentState":
        # Rebuild nested structures carefully
        alignment_data = data.get("alignment", {})
        emotion_data = data.get("emotion", {})
        complacence_data = emotion_data.get("complacence", {})
        tg_data = data.get("titanias_grace", {})
        boons_data = tg_data.get("boons", [])
        bb_data = data.get("bounce_back", {})
        inv_data = data.get("inventory", {})
        rels_raw = data.get("relationships", {})

        alignment = Alignment(
            law_axis=alignment_data.get("law_axis", "neutral"),
            moral_axis=alignment_data.get("moral_axis", "neutral"),
        )

        complacence = Complacence(
            mode=complacence_data.get("mode", "neutral"),
            level=float(complacence_data.get("level", 0.0)),
        )

        emotion = EmotionState(
            valence=float(emotion_data.get("valence", 0.0)),
            arousal=float(emotion_data.get("arousal", 0.0)),
            stance=float(emotion_data.get("stance", 0.0)),
            complacence=complacence,
            strain=float(emotion_data.get("strain", 0.0)),
            weird_mode=bool(emotion_data.get("weird_mode", False)),
        )

        tg = TitaniasGrace(
            class_name=tg_data.get("class_name", tg_data.get("class", "commoner")),
            job=tg_data.get("job", "villager"),
            level=int(tg_data.get("level", 1)),
            alignment_shift_tendency=tg_data.get("alignment_shift_tendency", "stable"),
            boons=[Boon(name=b.get("name", ""), rank=int(b.get("rank", 1))) for b in boons_data],
            fate_bias_toward_trust=float(tg_data.get("fate_bias_toward_trust", 0.0)),
            fate_bias_toward_betrayal=float(tg_data.get("fate_bias_toward_betrayal", 0.0)),
        )

        bb = BounceBack(
            resilience=float(bb_data.get("resilience", 0.5)),
            resentment=float(bb_data.get("resentment", 0.0)),
            cooldown=int(bb_data.get("cooldown", 0)),
        )

        inv = Inventory(
            gold=int(inv_data.get("gold", 0)),
            items=list(inv_data.get("items", [])),
        )

        relationships: Dict[str, RelationshipState] = {}
        for other_id, r in rels_raw.items():
            relationships[other_id] = RelationshipState(
                tier=r.get("tier", "stranger"),
                affinity=float(r.get("affinity", 0.0)),
                romantic=bool(r.get("romantic", False)),
            )

        return cls(
            id=data["id"],
            name=data["name"],
            kind=data.get("kind", "human"),
            tags=list(data.get("tags", [])),
            alignment=alignment,
            trust_strategy=data.get("trust_strategy", "copycat"),
            trust_matrix={k: float(v) for k, v in data.get("trust_matrix", {}).items()},
            gossip_bias={k: float(v) for k, v in data.get("gossip_bias", {}).items()},
            emotion=emotion,
            titanias_grace=tg,
            bounce_back=bb,
            inventory=inv,
            relationships=relationships,
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, s: str) -> "AgentState":
        return cls.from_dict(json.loads(s))

    # ----- relationship helpers -----

    def get_relationship(self, other_id: str) -> RelationshipState:
        if other_id not in self.relationships:
            self.relationships[other_id] = RelationshipState()
        return self.relationships[other_id]

    def set_relationship(
        self,
        other_id: str,
        tier: RelationshipTier,
        affinity: float,
        romantic: bool = False,
    ) -> None:
        self.relationships[other_id] = RelationshipState(
            tier=tier,
            affinity=max(-1.0, min(1.0, affinity)),
            romantic=romantic,
        )

    # ----- trust / emotion update math -----

    def get_trust(self, other_id: str) -> float:
        # baseline from gossip if no direct trust yet
        if other_id in self.trust_matrix:
            return self.trust_matrix[other_id]
        if other_id in self.gossip_bias:
            return self.gossip_bias[other_id]
        return 0.0

    def _align_weight(self) -> float:
        """
        Simple modifier from alignment: good -> more forgiving,
        evil -> harsher, lawful -> more sensitive to betrayal, etc.
        """
        w = 1.0
        if self.alignment.moral_axis == "good":
            w *= 0.8  # less harsh updates
        elif self.alignment.moral_axis == "evil":
            w *= 1.2  # harsher, less forgiving

        if self.alignment.law_axis == "lawful":
            w *= 1.1  # more sensitive to rule-breaking
        elif self.alignment.law_axis == "chaotic":
            w *= 0.9  # more tolerant of chaos
        return w

    def update_trust_after_interaction(self, other_id: str, outcome: float) -> None:
        """
        Update trust toward `other_id` based on the signed outcome:

        outcome:
          > 0  = good-for-me interaction (cooperation, mutual gain)
          < 0  = bad-for-me interaction (betrayal, loss)
          = 0  = neutral / ambiguous

        Design:
          - Negative events move trust faster than positive ones.
          - Titania's Grace can bias toward trust or toward betrayal.
          - Alignment (good/evil) slightly modulates how hard betrayal hits.
        """
        current = self.trust_matrix.get(other_id, 0.0)

        # Default learning rates
        pos_lr = 0.15
        neg_lr = 0.35
        neu_lr = 0.05

        # Titania's Grace biases
        grace = self.titanias_grace
        bias_trust = 0.0
        bias_betrayal = 0.0
        if grace is not None:
            bias_trust = grace.fate_bias_toward_trust
            bias_betrayal = grace.fate_bias_toward_betrayal

        if outcome > 0.0:
            lr = pos_lr * (1.0 + bias_trust)
        elif outcome < 0.0:
            lr = neg_lr * (1.0 + bias_betrayal)

            # Alignment sensitivity: good chars bruise more, evil chars shrug more
            if self.alignment.moral_axis == "good":
                lr *= 1.2
            elif self.alignment.moral_axis == "evil":
                lr *= 0.8
        else:
            lr = neu_lr

        delta = lr * outcome  # outcome already signed
        new_trust = current + delta

        # Clamp to [-1, 1]
        if new_trust > 1.0:
            new_trust = 1.0
        if new_trust < -1.0:
            new_trust = -1.0

        self.trust_matrix[other_id] = new_trust


    def apply_emotional_impact(
        self,
        payoff_emotion: float,
        betrayal: bool,
        other_id: str | None = None,
    ) -> None:
        """
        Update emotional state and bounce-back based on the emotional payoff
        of the round and whether this felt like a betrayal.

        payoff_emotion:
          roughly in [-1, +1] from the game outcome mapping.

        betrayal:
          True if I cooperated and the other defected.
        """
        # --- Valence update ---
        v = self.emotion.valence

        # Payoff contribution: mild but persistent
        v += 0.4 * payoff_emotion

        # Betrayal is a direct emotional sting
        if betrayal:
            v -= 0.3

        # Clamp valence
        if v > 1.0:
            v = 1.0
        if v < -1.0:
            v = -1.0

        self.emotion.valence = v

        # --- Strain update ---
        s = self.emotion.strain

        if betrayal:
            # Betrayal spikes strain; worse if we already distrust them
            distrust = 0.0
            if other_id is not None:
                distrust = max(0.0, -self.get_trust(other_id))  # in [0, 1]
            s += 0.2 + 0.1 * distrust
        else:
            # Good or neutral rounds bleed off strain gradually
            s *= 0.9

        if s > 1.0:
            s = 1.0
        if s < 0.0:
            s = 0.0

        self.emotion.strain = s

        # --- Resentment update (BounceBack) ---
        r = self.bounce_back.resentment

        if betrayal:
            # Betrayal adds a chunk of resentment but with some decay
            r = r * 0.8 + 0.25
        else:
            # Positive/neutral interaction slowly heals resentment
            r *= 0.9

        if r > 1.0:
            r = 1.0
        if r < 0.0:
            r = 0.0

        self.bounce_back.resentment = r

        # --- Weird mode toggle ---
        # Strong emotions (very high |valence|) or high strain can flip this on.
        if abs(v) > 0.95 or s > 0.7:
            self.emotion.weird_mode = True
        elif s < 0.3 and abs(v) < 0.7:
            # Calm + moderate emotions tends to turn weird_mode back off
            self.emotion.weird_mode = False




