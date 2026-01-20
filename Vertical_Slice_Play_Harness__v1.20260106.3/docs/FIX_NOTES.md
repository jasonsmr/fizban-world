# Fix Notes — Mountain Pass Harness (v1.20260106.3)

This pack is **non-canon**. It exists to playtest readability and consequence clarity.

## What changed (from earlier harness builds)

### 1) Every node now has a cause → effect → consequence chain
Each **LORE** block answers:
- **What** impossible thing happens (observable)
- **How** it affects travelers (effect on body/mind/gear)
- **What escalates** if you linger (exposure cost)
- **Why you care** (stakes)

Each **SYSTEM** block answers:
- **What just happened to you** (a concrete micro-event)
- **What it means right now** (immediate risk)
- **What happens if you stall** (escalation)
- **What you must decide** (A/B/C)

### 2) Inspect (I) always does something
- Every node has an `inspect` text.
- The simulator grants a **Clue** the first time you Inspect a node (and +2 XP).
- Clues are summarized and explained in Status (S).

### 3) Status (S) is readable, not raw data
- Shows HP/XP/Tokens + current tension/scarcity/rumor.
- Explains active status effects in plain language.
- Lists discovered clues and what they mean.

### 4) Scaled to 100 decisions
`RUN_001_mountain_pass.scene_nodes.jsonl` contains **100 nodes** (N001–N100).
This creates enough runway to evaluate pacing, repetition pressure, and escalation.

## How to run

```bash
tar -xzf Vertical_Slice_Play_Harness__v1.20260106.3.tar.gz
cd Vertical_Slice_Play_Harness__v1.20260106.3
python simulator.py --run RUN_001_mountain_pass --seed 401
```

Commands:
- `A/B/C` choose
- `I` inspect (gains clue once per node)
- `S` status
- `H` help
- `Q` quit
