#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_agent_config.py
----------------------

Small, opinionated schema for Fizban "agent configs".

Goal:
- A single JSON config per agent that can be:
  - hand-edited,
  - versioned in git,
  - fed into alignment/trust/fate engines.

We are *not* wiring directly into the existing math modules here yet.
This is a clean layer we can adapt as the math stabilizes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal

# --- Basic type aliases ---

LawChaos = Literal["LAWFUL", "NEUTRAL", "CHAOTIC"]
GoodEvil = Literal["GOOD", "NEUTRAL", "EVIL"]

StrategyName = Literal[
    "Copycat",
    "Cooperator",
    "Cheater",
    "Grudger",
    "Copykitten",
    "Simpleton",
    "Random",
    "Detective",
]

# --- Alignment & class layer -------------------------------------------------


@dataclass
class AlignmentConfig:
    law_chaos: LawChaos
    good_evil: GoodEvil
    label: str
    default_strategy: StrategyName

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "AlignmentConfig":
        return AlignmentConfig(
            law_chaos=d["law_chaos"],
            good_evil=d["good_evil"],
            label=d.get("label") or f"{d['law_chaos'].title()} {d['good_evil'].title()}",
            default_strategy=d.get("default_strategy", "Copycat"),
        )


@dataclass
class ClassConfig:
    dnd_class: str
    level: int = 1
    job_tags: List[str] = field(default_factory=list)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ClassConfig":
        return ClassConfig(
            dnd_class=d["dnd_class"],
            level=int(d.get("level", 1)),
            job_tags=list(d.get("job_tags") or []),
        )


# --- Trust baseline (per other-agent) ----------------------------------------


@dataclass
class TrustBaseline:
    """Baseline trust vs. a specific other agent.

    NOTE: these fields mirror what fizban_trust_math currently uses in its
    JSON output, but we're keeping this as a *config* layer only.
    """

    target: str  # name/ID of the other agent ("Puck", "Paladin", etc.)
    affinity: float = 0.0
    gossip_bias: float = 0.0
    awe: float = 0.0
    boredom: float = 0.0
    # Optional pre-seeded memories:
    betrayal_count: float = 0.0
    cooperation_streak: float = 0.0

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "TrustBaseline":
        return TrustBaseline(
            target=d["target"],
            affinity=float(d.get("affinity", 0.0)),
            gossip_bias=float(d.get("gossip_bias", 0.0)),
            awe=float(d.get("awe", 0.0)),
            boredom=float(d.get("boredom", 0.0)),
            betrayal_count=float(d.get("betrayal_count", 0.0)),
            cooperation_streak=float(d.get("cooperation_streak", 0.0)),
        )


# --- Fate baseline (Titania's Grace) -----------------------------------------


@dataclass
class FateBaseline:
    grace: float = 0.5          # Titania's favor
    bounce_back: float = 0.5    # recovery speed
    mental_strain: float = 0.0  # accumulated weirdness

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "FateBaseline":
        return FateBaseline(
            grace=float(d.get("grace", 0.5)),
            bounce_back=float(d.get("bounce_back", 0.5)),
            mental_strain=float(d.get("mental_strain", 0.0)),
        )


# --- Main AgentConfig --------------------------------------------------------


@dataclass
class AgentConfig:
    name: str
    alignment: AlignmentConfig
    klass: ClassConfig
    tags: List[str] = field(default_factory=list)
    trust_baselines: List[TrustBaseline] = field(default_factory=list)
    fate_baseline: FateBaseline = field(default_factory=FateBaseline)
    notes: Optional[str] = None

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "AgentConfig":
        return AgentConfig(
            name=d["name"],
            alignment=AlignmentConfig.from_dict(d["alignment"]),
            klass=ClassConfig.from_dict(d["class"]),
            tags=list(d.get("tags") or []),
            trust_baselines=[
                TrustBaseline.from_dict(tb) for tb in d.get("trust_baselines", [])
            ],
            fate_baseline=FateBaseline.from_dict(d.get("fate_baseline") or {}),
            notes=d.get("notes"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "alignment": asdict(self.alignment),
            "class": asdict(self.klass),
            "tags": list(self.tags),
            "trust_baselines": [asdict(tb) for tb in self.trust_baselines],
            "fate_baseline": asdict(self.fate_baseline),
            "notes": self.notes,
        }


# --- File helpers ------------------------------------------------------------


def load_agent_config(path: Path) -> AgentConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    return AgentConfig.from_dict(data)


def save_agent_config(cfg: AgentConfig, path: Path, overwrite: bool = False) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists (use overwrite=True)")
    path.write_text(json.dumps(cfg.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


# --- Tiny demo ----------------------------------------------------------------


def _demo() -> None:
    """Minimal self-test: build a Paladin + Puck config pair."""
    base_dir = Path(__file__).resolve().parent / "examples"
    base_dir.mkdir(parents=True, exist_ok=True)

    paladin = AgentConfig(
        name="Paladin",
        alignment=AlignmentConfig(
            law_chaos="LAWFUL",
            good_evil="GOOD",
            label="Lawful Good",
            default_strategy="Copykitten",
        ),
        klass=ClassConfig(
            dnd_class="paladin",
            level=3,
            job_tags=["tank", "frontline", "divine"],
        ),
        tags=["hero", "lawful_good"],
        trust_baselines=[
            TrustBaseline(
                target="Puck",
                affinity=0.0,
                awe=0.2,
                boredom=0.0,
            )
        ],
        fate_baseline=FateBaseline(grace=0.6, bounce_back=0.5, mental_strain=0.1),
        notes="Prototype paladin agent for Paladin/Puck trust scenarios.",
    )

    puck = AgentConfig(
        name="Puck",
        alignment=AlignmentConfig(
            law_chaos="CHAOTIC",
            good_evil="NEUTRAL",
            label="Chaotic Neutral",
            default_strategy="Random",
        ),
        klass=ClassConfig(
            dnd_class="rogue",
            level=2,
            job_tags=["thief", "trickster"],
        ),
        tags=["trickster", "chaotic_neutral"],
        trust_baselines=[
            TrustBaseline(
                target="Paladin",
                affinity=0.1,
                awe=0.4,
                boredom=0.1,
            )
        ],
        fate_baseline=FateBaseline(grace=0.55, bounce_back=0.6, mental_strain=0.05),
        notes="Prototype rogue/trickster agent.",
    )

    save_agent_config(paladin, base_dir / "agent_paladin_v2.json", overwrite=True)
    save_agent_config(puck, base_dir / "agent_puck_v2.json", overwrite=True)

    print("Wrote:")
    print(f" - {base_dir / 'agent_paladin_v2.json'}")
    print(f" - {base_dir / 'agent_puck_v2.json'}")


if __name__ == "__main__":
    _demo()

