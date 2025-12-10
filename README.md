# Fizban World

Fizban World is a prototype game-theory + emotion engine inspired by:

- D&D alignments (Law/Chaos × Good/Evil)
- Nicky Case’s *The Evolution of Trust* style strategies
- A Shakespearean pantheon (Oberon, Titania, Puck, Bottom, etc.)

## Layout

- `cli/`
  - `fizban_cli.py` — Termux-friendly OpenAI CLI (chat + responses)
- `config/`
  - `fizban_world_oberon.yaml` — Oberon flavor (game-theory architect)
  - `fizban_world_puck.yaml` — Puck flavor (emotion engine)
  - `robotforest_build.yaml` — RobotForest build engineer flavor
- `world/`
  - `fizban_alignment.py` — alignment labels & helper functions
  - `fizban_alignment_math.py` — numeric alignment grid + compatibility
  - `fizban_trust_math.py` — iterated trust engine math
  - `fizban_fate.py` — Titania’s Grace fate / weird-mode engine
  - `fizban_sim_round.py` — single-round sim utilities
  - `fizban_sim_series.py` — multi-round series utilities
  - `fizban_dialogue*.py` — narrative/diagnostic helpers
  - `examples/` — JSON/JSONL snapshots for Paladin/Puck scenarios

## Running demos

From the project root:

```bash
cd world
./fizban_alignment_math_demo.py
./fizban_trust_demo.py
./fizban_fate_demo.py

