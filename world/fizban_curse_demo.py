#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_curse_demo.py

Demo:
- Load Paladin v2 agent and all trees.
- Build a spread normally.
- Add a PATRON_LOCK curse against Oberon to the Paladin.
- Build a spread again and show that Oberon's trade card disappears,
  without removing any existing skills/boons.
"""

from __future__ import annotations

from pathlib import Path
import json

from fizban_level_menu import (
    _load_agent_from_v2,
    load_all_trees,
    build_tarot_spread,
)
from fizban_curse import add_curse


def _demo() -> int:
    base_dir = Path(__file__).resolve().parent
    examples_dir = base_dir / "examples"

    paladin_path = examples_dir / "agent_paladin_v2.json"

    paladin = _load_agent_from_v2(paladin_path)
    trees = load_all_trees(base_dir)

    # Spread BEFORE curse
    spread_before = build_tarot_spread(paladin, trees, num_cards=3)

    # Add a PATRON_LOCK curse against Oberon (e.g. for betraying him)
    oberon_curse = {
        "id": "CURSE_OBERON_TRADE_LOCK",
        "source": "Bottom",            # or "Oberon" if he's the punisher
        "type": "PATRON_LOCK",
        "target_patron": "Oberon",
        "duration_rounds": 20,
        "remaining_rounds": 10,
        # Example: only active in Oberon's domains
        # "while_location_tags": ["trade_district", "oberon_temple"],
        "severity": 0.8,
    }
    add_curse(paladin, oberon_curse)

    spread_after = build_tarot_spread(paladin, trees, num_cards=3)

    out = {
        "before_curse": spread_before,
        "after_curse": spread_after,
        "note": (
            "Notice that Oberon's Merchant's Mark disappears from the 'after_curse' "
            "spread, but existing skills/boons would stay on the agent. "
            "This is a freeze, not deletion."
        ),
    }

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_demo())

