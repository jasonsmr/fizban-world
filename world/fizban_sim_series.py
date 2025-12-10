#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_sim_series.py

Run a multi-round series of interactions between two Fizban agents.
Can optionally inject a hard betrayal round for agent B.

Usage:
  python3 fizban_sim_series.py a.json b.json \
      --rounds 20 \
      --betrayal-round-b 10 \
      --out-series series.jsonl \
      --out-a-final a_final.json \
      --out-b-final b_final.json
"""

import argparse
import json
from pathlib import Path
from typing import Optional

from fizban_agent import AgentState
from fizban_sim_round import run_round


def load_agent(path: Path) -> AgentState:
    data = json.loads(path.read_text(encoding="utf-8"))
    return AgentState.from_dict(data)


def save_agent(path: Path, agent: AgentState) -> None:
    path.write_text(agent.to_json(), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Run a multi-round Fizban interaction series.")
    ap.add_argument("agent_a", type=str, help="Path to agent A JSON")
    ap.add_argument("agent_b", type=str, help="Path to agent B JSON")
    ap.add_argument("--rounds", type=int, default=10, help="Number of rounds to run (default: 10)")
    ap.add_argument(
        "--betrayal-round-b",
        type=int,
        default=None,
        help="If set, on this round B will hard-defect (D) while A cooperates (C).",
    )
    ap.add_argument(
        "--out-series",
        type=str,
        default=None,
        help="If set, write per-round JSON lines to this file.",
    )
    ap.add_argument(
        "--out-a-final",
        type=str,
        default=None,
        help="Where to write final agent A JSON.",
    )
    ap.add_argument(
        "--out-b-final",
        type=str,
        default=None,
        help="Where to write final agent B JSON.",
    )
    args = ap.parse_args()

    path_a = Path(args.agent_a).expanduser().resolve()
    path_b = Path(args.agent_b).expanduser().resolve()

    agent_a = load_agent(path_a)
    agent_b = load_agent(path_b)

    series_fp = None
    if args.out_series:
        series_path = Path(args.out_series).expanduser().resolve()
        series_fp = series_path.open("w", encoding="utf-8")

    for i in range(args.rounds):
        round_num = i + 1

        forced_a: Optional[str] = None
        forced_b: Optional[str] = None
        betrayal_injected = False

        if args.betrayal_round_b is not None and round_num == args.betrayal_round_b:
            # Narrative: A keeps faith, B suddenly stabs them in the back.
            forced_a = "C"
            forced_b = "D"
            betrayal_injected = True

        summary, agent_a, agent_b = run_round(
            agent_a,
            agent_b,
            forced_action_a=forced_a,
            forced_action_b=forced_b,
        )

        summary["round"] = round_num
        summary["betrayal_injected_b"] = betrayal_injected

        if series_fp is not None:
            series_fp.write(json.dumps(summary, ensure_ascii=False) + "\n")

    if series_fp is not None:
        series_fp.close()

    # Save finals
    if args.out_a_final:
        save_agent(Path(args.out_a_final).expanduser().resolve(), agent_a)
    if args.out_b_final:
        save_agent(Path(args.out_b_final).expanduser().resolve(), agent_b)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

