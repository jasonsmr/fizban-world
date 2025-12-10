#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fizban_dnd_mapping_demo.py
--------------------------

Thin wrapper around fizban_dnd_mapping._demo() so you can run:

    ./fizban_dnd_mapping_demo.py

without exposing the internal helper.
"""

from fizban_dnd_mapping import _demo


def main() -> None:
    _demo()


if __name__ == "__main__":
    main()

