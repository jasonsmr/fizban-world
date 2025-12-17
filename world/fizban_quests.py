#!/usr/bin/env python3
"""
fizban_quests.py - Patron-driven quest offers for Fizban World.

This is intentionally self-contained:
- No imports from other Fizban modules.
- Designed to be easy to wire into world_state later.

Core idea:
- Given an agent snapshot (name, level, traits, favor_per_patron),
  generate a list of "quest offers" from Titans (Titania/Oberon/Bottom),
  King/Queen, and the Lovers.

Each quest offer includes:
- id, title, patron, target (if any), danger, reward hooks, and
  some story flavor tags for later AI narration.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Any


# ----- Data structures ------------------------------------------------------


@dataclass
class QuestRequirements:
    min_level: int = 1
    min_favor: float = 0.0  # for the patron making the offer
    required_traits_any: List[str] | None = None
    required_traits_all: List[str] | None = None


@dataclass
class QuestReward:
    # These are *hooks*; engine or DM can interpret them:
    favor_delta: Dict[str, float]
    grant_traits: List[str]
    grant_abilities: List[str]
    notes: str


@dataclass
class QuestTemplate:
    id: str
    title: str
    patron: str
    target_patron: str | None
    danger: str  # "low", "medium", "high"
    tags: List[str]
    summary: str
    requirements: QuestRequirements
    reward: QuestReward


@dataclass
class QuestOffer:
    id: str
    title: str
    patron: str
    target_patron: str | None
    agent: str
    danger: str
    tags: List[str]
    summary: str
    reward: Dict[str, Any]
    requirements: Dict[str, Any]


# ----- Quest template library ----------------------------------------------


def _build_quest_templates() -> List[QuestTemplate]:
    """
    A small, opinionated library of quests that match your lore:

    - Titania: "protect forest / heal weirdness"
    - Oberon: trade, contracts, markets, balanced order
    - Bottom: chaos, pranks, social inversion
    - Lovers: bonds, betrayals, high-risk romance quests
    - King/Queen: kingdom stability, law vs weird, research of strange magic
    """
    templates: List[QuestTemplate] = []

    # Titania: basic grace quest
    templates.append(
        QuestTemplate(
            id="Q_TITANIA_HEART_OF_THE_GROVE",
            title="Heart of the Grove",
            patron="Titania",
            target_patron=None,
            danger="medium",
            tags=["titania", "forest", "healing", "grace"],
            summary=(
                "A sacred grove is faltering under subtle corruption. "
                "Titania asks you to cleanse it without burning or butchering the land."
            ),
            requirements=QuestRequirements(
                min_level=3,
                min_favor=0.4,
                required_traits_any=["titania_favored", "forest_child", "bloodline_forest_heir_druidic"],
                required_traits_all=None,
            ),
            reward=QuestReward(
                favor_delta={"Titania": 0.15},
                grant_traits=["titania_blessed_grovewalker"],
                grant_abilities=["grove_step", "soothing_leaf_aura"],
                notes="Completing this should also slightly nudge weird/grace in fate engine.",
            ),
        )
    )

    # Oberon: merchant oath quest
    templates.append(
        QuestTemplate(
            id="Q_OBERON_MERCHANT_OATH",
            title="Oberon's Merchant Oath",
            patron="Oberon",
            target_patron=None,
            danger="low",
            tags=["oberon", "contract", "trade", "oath"],
            summary=(
                "Oberon offers a trade route and a binding oath: safeguard a caravan "
                "through dangerous woods, and swear to never abuse your market power."
            ),
            requirements=QuestRequirements(
                min_level=5,
                min_favor=0.5,
                required_traits_any=["oberon_favored", "merchant", "lawful_good"],
                required_traits_all=None,
            ),
            reward=QuestReward(
                favor_delta={"Oberon": 0.2},
                grant_traits=["oberon_oathbound_merchant"],
                grant_abilities=["sense_unfair_deal", "contract_binding_glow"],
                notes="Pairs well with Oberon trade tree: unlocks better trade boons.",
            ),
        )
    )

    # Bottom: masquerade chaos quest
    templates.append(
        QuestTemplate(
            id="Q_BOTTOM_MASQUERADE",
            title="Night of the Masquerade",
            patron="Bottom",
            target_patron=None,
            danger="medium",
            tags=["bottom", "chaos", "masquerade", "weird"],
            summary=(
                "Bottom invites you to a masked festival where roles invert: nobles "
                "serve peasants, and truths are spoken only in riddles. Survive the "
                "night without losing yourself."
            ),
            requirements=QuestRequirements(
                min_level=4,
                min_favor=0.5,
                required_traits_any=["bottom_favored", "trickster", "chaotic_neutral"],
                required_traits_all=None,
            ),
            reward=QuestReward(
                favor_delta={"Bottom": 0.25},
                grant_traits=["bottom_masquerade_survivor"],
                grant_abilities=["mask_of_many_faces_minor"],
                notes="Ideal hook to increase weird_mode bias for an agent.",
            ),
        )
    )

    # Lovers: betrayal-heavy quest between patrons
    templates.append(
        QuestTemplate(
            id="Q_LOVERS_STOLEN_VOW",
            title="Stolen Vows",
            patron="Lovers",
            target_patron="Titania",
            danger="high",
            tags=["lovers", "betrayal", "romance", "gods_conflict"],
            summary=(
                "Lovers ask you to officiate a secret union that defies Titania's designs. "
                "If you succeed, a powerful bond is forged—but Titania may never forgive you."
            ),
            requirements=QuestRequirements(
                min_level=12,
                min_favor=0.6,
                required_traits_any=["lovers_favored", "hero", "seducer"],
                required_traits_all=None,
            ),
            reward=QuestReward(
                favor_delta={"Lovers": 0.3, "Titania": -0.2},
                grant_traits=["lovers_confidant"],
                grant_abilities=["charm_bonded_pair"],
                notes=(
                    "Pairs well with betrayal_offer system: Titania can curse or freeze "
                    "Titania-linked boons afterwards."
                ),
            ),
        )
    )

    # King: kingdom defense quest
    templates.append(
        QuestTemplate(
            id="Q_KING_DEFEND_BORDER",
            title="Defend the Border",
            patron="King",
            target_patron=None,
            danger="medium",
            tags=["king", "war", "kingdom", "duty"],
            summary=(
                "King calls upon you to defend a border village from encroaching monsters. "
                "Hold the line and inspire the common folk."
            ),
            requirements=QuestRequirements(
                min_level=8,
                min_favor=0.4,
                required_traits_any=["king_chosen", "hero", "devout"],
                required_traits_all=None,
            ),
            reward=QuestReward(
                favor_delta={"King": 0.25},
                grant_traits=["defender_of_the_realm"],
                grant_abilities=["rally_civilians", "banner_of_courage"],
                notes="This is a great milestone quest for Paladin or similar classes.",
            ),
        )
    )

    # Queen: weird research / psionic quest
    templates.append(
        QuestTemplate(
            id="Q_QUEEN_STUDY_THE_WEIRD",
            title="Study the Weird",
            patron="Queen",
            target_patron=None,
            danger="high",
            tags=["queen", "weird", "psionic", "research"],
            summary=(
                "Queen has noticed rising strange states in the forest. She asks you to "
                "deliberately provoke and record weird phenomena without letting them "
                "consume you."
            ),
            requirements=QuestRequirements(
                min_level=10,
                min_favor=0.4,
                required_traits_any=["queen_favored", "psionic", "embraces_chaos"],
                required_traits_all=None,
            ),
            reward=QuestReward(
                favor_delta={"Queen": 0.3},
                grant_traits=["queen_weird_researcher"],
                grant_abilities=["stabilize_weird_field", "detect_psionic_residue"],
                notes="Perfect hook for weird/strain mechanics and future psionic trees.",
            ),
        )
    )

    return templates


QUEST_TEMPLATES: List[QuestTemplate] = _build_quest_templates()


# ----- Core engine: filtering & generation ----------------------------------


def _agent_meets_requirements(
    level: int,
    traits: List[str],
    patron_favor: float,
    req: QuestRequirements,
) -> bool:
    if level < req.min_level:
        return False
    if patron_favor < req.min_favor:
        return False

    traits_set = set(traits)

    if req.required_traits_any:
        if not traits_set.intersection(req.required_traits_any):
            return False

    if req.required_traits_all:
        if not set(req.required_traits_all).issubset(traits_set):
            return False

    return True


def generate_quests_for_agent(
    *,
    agent_name: str,
    level: int,
    traits: List[str],
    favor: Dict[str, float],
) -> List[QuestOffer]:
    """
    Given an agent snapshot, return a list of quest offers from patrons.

    Parameters
    ----------
    agent_name: str
        "Paladin", "Puck", etc.
    level: int
        Current level of the agent (we'll eventually sync this to world_state).
    traits: List[str]
        Agent traits, e.g. ["lawful_good", "titania_favored", "hero"].
    favor: Dict[str, float]
        Map patron -> favor score (0.0 to 1.0 recommended).
    """
    offers: List[QuestOffer] = []

    for tmpl in QUEST_TEMPLATES:
        patron = tmpl.patron
        patron_favor = favor.get(patron, 0.0)

        if not _agent_meets_requirements(level, traits, patron_favor, tmpl.requirements):
            continue

        offer = QuestOffer(
            id=tmpl.id,
            title=tmpl.title,
            patron=tmpl.patron,
            target_patron=tmpl.target_patron,
            agent=agent_name,
            danger=tmpl.danger,
            tags=list(tmpl.tags),
            summary=tmpl.summary,
            reward=asdict(tmpl.reward),
            requirements=asdict(tmpl.requirements),
        )
        offers.append(offer)

    # Sort by "importance": higher favor with that patron, then danger
    danger_weight = {"low": 0.0, "medium": 0.5, "high": 1.0}

    def _score(o: QuestOffer) -> float:
        fav = favor.get(o.patron, 0.0)
        return fav * 1.0 + danger_weight.get(o.danger, 0.0) * 0.1

    offers.sort(key=_score, reverse=True)
    return offers


__all__ = [
    "QuestRequirements",
    "QuestReward",
    "QuestTemplate",
    "QuestOffer",
    "QUEST_TEMPLATES",
    "generate_quests_for_agent",
]

