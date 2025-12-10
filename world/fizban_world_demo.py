#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_world_demo.py
--------------------

High-level demo:

- Load AgentConfig for Paladin & Puck.
- Initialize world_state.
- Run a scripted interaction pattern.
- Print final world snapshot + history + destiny rolls as JSON.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from fizban_agent_config import load_agent_config
from fizban_world_state import (
    init_world_from_configs,
    play_interaction,
    world_to_dict,
    destiny_roll_for_pair,
)


def run_script(script: List[str]) -> dict:
    base = Path(__file__).resolve().parent
    examples = base / "examples"

    pal_cfg = load_agent_config(examples / "agent_paladin_v2.json")
    puck_cfg = load_agent_config(examples / "agent_puck_v2.json")

    world = init_world_from_configs([pal_cfg, puck_cfg])

    for oc in script:
        play_interaction(world, "Paladin", "Puck", oc)

    destiny = destiny_roll_for_pair(world, "Paladin", "Puck", dc=12)

    return {
        "world_final": world_to_dict(world),
        "history": world.history,
        "destiny": destiny,
        "script": script,
    }


def main() -> None:
    # Same pattern you've been using in trust/fate demos:
    script = ["CC", "CC", "CC", "CD", "CC"]

    result = run_script(script)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

