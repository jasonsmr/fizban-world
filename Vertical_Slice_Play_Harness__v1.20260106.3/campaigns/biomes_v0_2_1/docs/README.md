# Biomes Pack v0.1

This pack contains 200 connected biomes, grouped into 10 campaigns (20 biomes each).

Notes:
- You referenced `RUN_001_mountain_pass.scene`. I don't have the exact schema for that scene file here,
  so the records include a conservative `seed_scene_ref` field plus engine-friendly fields:
  connections, POI seeds, faction + quest bindings, and generator hints.
- Graph constraint: each biome connects to 2–5 others; overall graph is connected.

## Files
- packs/biomes.jsonl — 200 biome records
- packs/campaigns.jsonl — 10 campaign arcs
- packs/quests.jsonl — 200 quest records (1 per biome)
- packs/bindings.jsonl — biome → factions → quests binding
- packs/map_graph.json — node degrees + undirected edge list
- packs/generator_rules.json — procedural generation constraints & parameters

## Quick validation
- Degree cap: 5
- Connected: yes (constructed from a chain + extra edges)
