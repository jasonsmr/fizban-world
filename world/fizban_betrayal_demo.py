#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_betrayal_demo.py

Pretend Paladin is high-level and see what betrayal quests the gods
would tempt them with.
"""

from __future__ import annotations

from pathlib import Path
import json

from fizban_level_menu import _load_agent_from_v2
from fizban_gods import compute_favor_for_agent
from fizban_betrayal_offers import get_betrayal_offers


def _demo() -> int:
    base_dir = Path(__file__).resolve().parent
    examples_dir = base_dir / "examples"

    paladin_path = examples_dir / "agent_paladin_v2.json"
    paladin = _load_agent_from_v2(paladin_path)

    # Pretend they are level 120 for demo purposes
    paladin["class"]["level"] = 120

    favors = compute_favor_for_agent(paladin)
    paladin["favor"] = favors

    offers = get_betrayal_offers(paladin, min_level=100)

    out = {
        "paladin_level": paladin["class"]["level"],
        "favor": favors,
        "offers": offers,
    }

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_demo())

