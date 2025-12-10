#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_series_stats.py

Read a Fizban interaction series JSONL file and print a compact summary:
- rounds
- betrayals by A and B
- injected betrayals (if any)
- trust evolution for A and B
- emotional valence evolution for A and B

Usage:
  python3 fizban_series_stats.py path/to/series.jsonl
"""

import argparse
import json
from pathlib import Path
from statistics import mean


def load_series(path: Path):
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _safe_mean(values):
    if not values:
        return None
    return mean(values)


def summarize_series(records):
    if not records:
        return {"error": "empty_series"}

    # Assume consistent schema
    first = records[0]
    last = records[-1]

    a_id = first.get("a_id", "A")
    b_id = first.get("b_id", "B")

    rounds = len(records)

    betrayals_a = sum(1 for r in records if r.get("betrayal_a"))
    betrayals_b = sum(1 for r in records if r.get("betrayal_b"))
    injected_betrayals_b = sum(
        1 for r in records if r.get("betrayal_injected_b")
    )

    trust_a_vals = [r.get("trust_a_after", 0.0) for r in records]
    trust_b_vals = [r.get("trust_b_after", 0.0) for r in records]

    val_a_vals = [r.get("emotion_a_valence", 0.0) for r in records]
    val_b_vals = [r.get("emotion_b_valence", 0.0) for r in records]

    summary = {
        "a_id": a_id,
        "b_id": b_id,
        "rounds": rounds,
        "betrayals": {
            "a": betrayals_a,
            "b": betrayals_b,
            "b_injected_scripted": injected_betrayals_b,
        },
        "trust_a": {
            "start": trust_a_vals[0],
            "end": trust_a_vals[-1],
            "min": min(trust_a_vals),
            "max": max(trust_a_vals),
            "avg": _safe_mean(trust_a_vals),
        },
        "trust_b": {
            "start": trust_b_vals[0],
            "end": trust_b_vals[-1],
            "min": min(trust_b_vals),
            "max": max(trust_b_vals),
            "avg": _safe_mean(trust_b_vals),
        },
        "emotion_valence_a": {
            "start": val_a_vals[0],
            "end": val_a_vals[-1],
            "min": min(val_a_vals),
            "max": max(val_a_vals),
            "avg": _safe_mean(val_a_vals),
        },
        "emotion_valence_b": {
            "start": val_b_vals[0],
            "end": val_b_vals[-1],
            "min": min(val_b_vals),
            "max": max(val_b_vals),
            "avg": _safe_mean(val_b_vals),
        },
    }

    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Summarize a Fizban series JSONL file.")
    ap.add_argument(
        "series",
        type=str,
        help="Path to JSONL series file (one JSON record per line)",
    )
    args = ap.parse_args()

    path = Path(args.series).expanduser().resolve()
    if not path.is_file():
        print(json.dumps({"error": f"no_such_file: {path}"}))
        return 1

    records = load_series(path)
    summary = summarize_series(records)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

