#!/usr/bin/env python3
"""
fizban_monsters_demo.py

Demo: generate a few encounters from the bestiary for different regions
and difficulties, using difficulty_profile.json.
"""

from __future__ import annotations

import json

from fizban_monsters import build_encounter, encounter_to_dict


def main() -> None:
  party = [
    {"name": "Paladin", "level": 5},
    {"name": "Puck", "level": 4},
  ]

  enc_forest_easy = build_encounter(
    party=party,
    region_id="STARTING_FOREST",
    difficulty="easy",
  )
  enc_forest_hard = build_encounter(
    party=party,
    region_id="STARTING_FOREST",
    difficulty="hard",
  )
  enc_border_medium = build_encounter(
    party=party,
    region_id="KINGDOM_BORDER",
    difficulty="medium",
  )

  out = {
    "forest_easy": encounter_to_dict(enc_forest_easy),
    "forest_hard": encounter_to_dict(enc_forest_hard),
    "border_medium": encounter_to_dict(enc_border_medium),
  }
  print(json.dumps(out, indent=2))


if __name__ == "__main__":
  main()

