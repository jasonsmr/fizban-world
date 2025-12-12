#!/usr/bin/env python3
"""
fizban_encounter_quests_demo.py

Tiny wrapper to print the demo payload as JSON
so you can pipe to jq.
"""

import json
from fizban_encounter_quests import demo_payload


def main() -> None:
    data = demo_payload()
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()

