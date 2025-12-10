#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_traits_demo.py

Preview trait derivation for Paladin + Puck.
"""

from __future__ import annotations

from pathlib import Path
import json

from fizban_level_menu import _load_agent_from_v2
from fizban_traits import derive_traits_for_agent


def _demo() -> int:
    base_dir = Path(__file__).resolve().parent
    examples = base_dir / "examples"

    paladin = _load_agent_from_v2(examples / "agent_paladin_v2.json")
    puck = _load_agent_from_v2(examples / "agent_puck_v2.json")

    paladin_traits = derive_traits_for_agent(paladin)
    puck_traits = derive_traits_for_agent(puck)

    out = {
        "paladin_traits": paladin_traits,
        "puck_traits": puck_traits,
    }

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_demo())

