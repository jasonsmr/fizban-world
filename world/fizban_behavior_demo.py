#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_behavior_demo.py

Show how Paladin vs Puck get different strategy profiles
from their tags/class/alignment.
"""

from __future__ import annotations

from pathlib import Path
import json

from fizban_level_menu import _load_agent_from_v2
from fizban_behavior import build_strategy_profile


def _demo() -> int:
    base_dir = Path(__file__).resolve().parent
    examples_dir = base_dir / "examples"

    paladin_path = examples_dir / "agent_paladin_v2.json"
    puck_path = examples_dir / "agent_puck_v2.json"

    paladin = _load_agent_from_v2(paladin_path)
    puck = _load_agent_from_v2(puck_path)

    out = {
        "paladin_behavior": build_strategy_profile(paladin),
        "puck_behavior": build_strategy_profile(puck),
    }

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_demo())

