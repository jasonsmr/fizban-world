# Biomes Pack v0.2.1 — Design Notes

This revision is a content + authoring upgrade driven by the RUN_001_mountain_pass playtest.

## Key fixes

- **Anti-monotony beats**: inject NEMESIS / PUZZLE / REVELATION / SANCTUARY every ~12 nodes.
- **Inspect has a cost**: Inspect trades attention/time (tension or scarcity) for certainty.
- **Recovery exists**: sanctuaries allow limited de-escalation.
- **Facts/locks drive progress**: campaigns should commit to new truths at major beats.
- **NPCs appear**: minimal NPC state must surface in narration at nemesis beats.

## Authoring surface: ws_effects

At node level or choice level, authors may add:

- `ws_effects.q2_mutations` (<=2 per beat)
- `ws_effects.facts_add` / `locks_add` / `status_add`

The simulator should translate these into WorldState mutations/flag_add operations.

## Content guidance

Avoid repeating the same lore/system cadence for every node.
Use:
- micro-puzzles (timing, rhythm, pattern)
- interrupts (watcher/ambush/negotiation)
- readable tells (clues make choices informative)
- stakes clocks (what happens if you stall)
