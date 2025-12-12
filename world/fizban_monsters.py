#!/usr/bin/env python3
"""
fizban_monsters.py

Bestiary + encounter generator hooked into:
 - monsters/core_bestary.json
 - difficulty_profile.json

This does NOT assign XP to agents (that's fizban_xp's job), but it computes
an XP budget and a concrete monster group.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


ROOT = Path(__file__).resolve().parent
BESTIARY_PATH = ROOT / "monsters" / "core_bestary.json"
DIFFICULTY_PROFILE_PATH = ROOT / "difficulty_profile.json"


@dataclass
class MonsterArchetype:
  id: str
  name: str
  cr: float
  base_xp: int
  role: str
  type: str
  tags: List[str]
  alignment_hint: str
  region_tags: List[str]
  behavior_hint: Dict[str, Any]

  @staticmethod
  def from_dict(d: Dict[str, Any]) -> "MonsterArchetype":
    return MonsterArchetype(
      id=d["id"],
      name=d["name"],
      cr=float(d["cr"]),
      base_xp=int(d["base_xp"]),
      role=d.get("role", "standard"),
      type=d.get("type", "unknown"),
      tags=list(d.get("tags", [])),
      alignment_hint=d.get("alignment_hint", "unaligned"),
      region_tags=list(d.get("region_tags", [])),
      behavior_hint=dict(d.get("behavior_hint", {})),
    )


@dataclass
class EncounterMonster:
  archetype_id: str
  name: str
  count: int
  cr: float
  role: str
  tags: List[str]
  xp_each: int
  xp_total: int


@dataclass
class EncounterSeed:
  region_id: str
  target_difficulty: str
  party: List[Dict[str, Any]]
  monsters: List[EncounterMonster]
  xp_budget_target: int
  xp_budget_actual: int
  notes: List[str]


def load_bestiary(path: Path = BESTIARY_PATH) -> Dict[str, MonsterArchetype]:
  data = json.loads(path.read_text())
  result: Dict[str, MonsterArchetype] = {}
  for mid, mdata in data.items():
    result[mid] = MonsterArchetype.from_dict(mdata)
  return result


def load_difficulty_profile(path: Path = DIFFICULTY_PROFILE_PATH) -> Dict[str, Any]:
  return json.loads(path.read_text())


def _xp_threshold_per_level(level: int, difficulty: str) -> int:
  """
  Rough XP thresholds per character per difficulty, inspired by 5e values
  but simplified and fuzzed for our purposes.
  """
  # Baseline: easy ~25*lvl, medium ~50*lvl, hard ~75*lvl, deadly ~100*lvl
  base = level * 25
  if difficulty == "easy":
    return base
  if difficulty == "medium":
    return base * 2
  if difficulty == "hard":
    return base * 3
  if difficulty == "deadly":
    return base * 4
  return base * 2  # default medium-ish


def _target_xp_budget(party_levels: List[int], difficulty: str, world_scalar: float) -> int:
  per_char = sum(_xp_threshold_per_level(lv, difficulty) for lv in party_levels)
  return int(per_char * world_scalar)


def _candidate_monsters_for_region(
  bestiary: Dict[str, MonsterArchetype],
  region_id: str,
  desired_cr_min: float,
  desired_cr_max: float,
  required_tags: Optional[List[str]] = None,
) -> List[MonsterArchetype]:
  required_tags = required_tags or []
  out: List[MonsterArchetype] = []
  for m in bestiary.values():
    if region_id not in m.region_tags:
      continue
    if m.cr < desired_cr_min or m.cr > desired_cr_max:
      continue
    if required_tags and not any(t in m.tags for t in required_tags):
      continue
    out.append(m)
  return out


def _cr_band_for_region(
  profile: Dict[str, Any],
  region_id: str,
  avg_party_level: float,
) -> Tuple[float, float]:
  regions = profile.get("regions", {})
  r = regions.get(region_id)
  if not r:
    # fallback: soft band around avg party level
    base_cr = max(0.25, avg_party_level * 0.75)
    return base_cr - 1.0, base_cr + 1.0

  base_cr = float(r.get("base_cr", 1.0))
  cr_var = float(r.get("cr_variance", 1.0))
  min_lvl = float(r.get("min_level", 1))

  # Nudge CR up very gently as party outgrows region min level
  lvl_delta = max(0.0, avg_party_level - min_lvl)
  base_cr = base_cr + 0.25 * lvl_delta
  return max(0.125, base_cr - cr_var), max(0.25, base_cr + cr_var)


def build_encounter(
  party: List[Dict[str, Any]],
  region_id: str,
  difficulty: str = "medium",
  required_tags: Optional[List[str]] = None,
  rng: Optional[random.Random] = None,
) -> EncounterSeed:
  """
  party: list of {"name": ..., "level": int}
  region_id: key from difficulty_profile["regions"]
  difficulty: "easy" | "medium" | "hard" | "deadly"
  required_tags: optional monster tag filter (e.g., ["goblin"], ["cult"])
  """
  rng = rng or random.Random()
  bestiary = load_bestiary()
  profile = load_difficulty_profile()

  party_levels = [int(p["level"]) for p in party]
  avg_lvl = sum(party_levels) / max(1, len(party_levels))

  # Global world difficulty scalar from profile
  global_profile = profile.get("global", {})
  world_scalar = float(global_profile.get("world_difficulty_scalar", 1.0))

  xp_target = _target_xp_budget(party_levels, difficulty, world_scalar)
  cr_min, cr_max = _cr_band_for_region(profile, region_id, avg_lvl)

  candidates = _candidate_monsters_for_region(
    bestiary,
    region_id=region_id,
    desired_cr_min=cr_min,
    desired_cr_max=cr_max,
    required_tags=required_tags,
  )
  if not candidates:
    # last-resort fallback: any monster in bestiary
    candidates = list(bestiary.values())

  monsters_out: List[EncounterMonster] = []
  xp_accum = 0
  notes: List[str] = []

  # Bias: at most 1 elite per encounter by default
  elites_used = 0

  # Greedy fill: add monsters until we hit ~70–110% of target
  attempts = 0
  while xp_accum < xp_target * 0.7 and attempts < 50:
    attempts += 1
    m = rng.choice(candidates)

    # Role-based count suggestion
    if m.role == "minion":
      count = rng.randint(2, 5)
    elif m.role in ("standard", "skirmisher", "controller"):
      count = rng.randint(1, 3)
    elif m.role == "elite":
      if elites_used >= 1:
        continue
      count = 1
      elites_used += 1
    else:
      count = 1

    xp_add = m.base_xp * count
    if xp_accum + xp_add > xp_target * 1.1 and monsters_out:
      # skip if this would overshoot too hard and we already have stuff
      continue

    monsters_out.append(
      EncounterMonster(
        archetype_id=m.id,
        name=m.name,
        count=count,
        cr=m.cr,
        role=m.role,
        tags=m.tags,
        xp_each=m.base_xp,
        xp_total=m.base_xp * count,
      )
    )
    xp_accum += xp_add

  if not monsters_out and candidates:
    # ensure at least one monster
    m = rng.choice(candidates)
    monsters_out.append(
      EncounterMonster(
        archetype_id=m.id,
        name=m.name,
        count=1,
        cr=m.cr,
        role=m.role,
        tags=m.tags,
        xp_each=m.base_xp,
        xp_total=m.base_xp,
      )
    )
    xp_accum = m.base_xp

  notes.append(
    f"avg_party_level={avg_lvl:.2f}, cr_band=[{cr_min:.2f}, {cr_max:.2f}], "
    f"xp_target={xp_target}, xp_actual={xp_accum}"
  )

  return EncounterSeed(
    region_id=region_id,
    target_difficulty=difficulty,
    party=party,
    monsters=monsters_out,
    xp_budget_target=xp_target,
    xp_budget_actual=xp_accum,
    notes=notes,
  )


def encounter_to_dict(enc: EncounterSeed) -> Dict[str, Any]:
  return {
    "region_id": enc.region_id,
    "target_difficulty": enc.target_difficulty,
    "party": enc.party,
    "xp_budget": {
      "target": enc.xp_budget_target,
      "actual": enc.xp_budget_actual,
    },
    "monsters": [asdict(m) for m in enc.monsters],
    "notes": enc.notes,
  }


if __name__ == "__main__":
  # Tiny smoke test if you run this directly.
  party = [
    {"name": "Paladin", "level": 5},
    {"name": "Puck", "level": 4},
  ]
  enc = build_encounter(
    party=party,
    region_id="STARTING_FOREST",
    difficulty="medium",
  )
  print(json.dumps(encounter_to_dict(enc), indent=2))

