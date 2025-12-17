#!/usr/bin/env python3

import json
import sys

from fizban_oracle import build_default_oracle_payload


def main() -> None:
    payload = build_default_oracle_payload(
        focus_agent="Paladin",
        max_cards=3,
    )

    # For now just print the spread; caller can pipe to jq or UI.
    json.dump(payload["oracle_spread"], sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()

