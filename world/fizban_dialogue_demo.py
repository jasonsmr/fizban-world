#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from pathlib import Path

from fizban_agent import AgentState
from fizban_dialogue import compute_dialogue_slots


def load_agent(path: str) -> AgentState:
    p = Path(path).expanduser().resolve()
    data = json.loads(p.read_text(encoding="utf-8"))
    return AgentState.from_dict(data)


def main() -> int:
    ap = argparse.ArgumentParser(description="Show dialogue slots A->B for two Fizban agents.")
    ap.add_argument("agent_a", type=str, help="Path to agent A JSON")
    ap.add_argument("agent_b", type=str, help="Path to agent B JSON")
    args = ap.parse_args()

    a = load_agent(args.agent_a)
    b = load_agent(args.agent_b)

    result = compute_dialogue_slots(a, b)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

