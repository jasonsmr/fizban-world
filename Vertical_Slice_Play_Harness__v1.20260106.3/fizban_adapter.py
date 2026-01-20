# fizban_adapter.py
from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from worldstate_v0_1 import WorldState, apply_mutations

def rumor_rebound_mutations(ws: WorldState) -> List[Dict[str, Any]]:
    """
    If any faction rumor hits +5 or -5, spill 1 step toward nearby factions.
    We keep it Q2-safe: this helper returns AT MOST 2 mutations (pick most important).
    """
    muts: List[Dict[str, Any]] = []
    # naive adjacency: share prefix group "xi.faction." -> spill to top 2 others
    extremes = []
    for k,v in ws.rumor_pressure.items():
        if v >= 5 or v <= -5:
            extremes.append((k,v))
    if not extremes:
        return muts

    # Pick the strongest extreme
    extremes.sort(key=lambda kv: abs(kv[1]), reverse=True)
    src, val = extremes[0]
    direction = 1 if val > 0 else -1

    # spill to two other factions (if exist)
    candidates = [k for k in ws.rumor_pressure.keys() if k != src]
    for dst in candidates[:2]:
        muts.append({"op":"inc" if direction>0 else "dec", "path":f"/rumor_pressure/{dst}", "value":1})
        if len(muts) >= 2:
            break
    return muts

def fizban_decide(choice: Dict[str, Any], ws: WorldState, npc_snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    STUB: replace internals later with real Fizban world modules.
    Must return:
      - q2_mutations (<=2)
      - optional lattice_lines, lore_shard, npc_deltas
    """
    # Example heuristic: choices can carry tags like "risk", "mercy", "theft"
    tags = set(choice.get("tags", []) or [])
    muts: List[Dict[str, Any]] = []

    if "risk" in tags:
        muts.append({"op":"inc", "path":"/tension_index", "value":4})
    if "quiet" in tags:
        muts.append({"op":"band_shift", "path":"/scarcity_vector/noise_budget", "value":-1})
    if "theft" in tags:
        muts.append({"op":"dec", "path":"/rumor_pressure/xi.faction.local", "value":1})
    if "mercy" in tags:
        muts.append({"op":"inc", "path":"/rumor_pressure/xi.faction.local", "value":1})

    # enforce Q2 cap by priority
    muts = muts[:2]

    # optional: rebound as a second beat later; do not auto-apply here if it would exceed cap
    lattice_lines = []
    if ws.tension_index >= 70:
        lattice_lines.append("The air is brittle. Pick clean actions or you’ll pay twice.")
    if "SHADOW_SICKNESS" in ws.flags.status:
        lattice_lines.append("Your shadow still clings. People notice before they understand.")

    return {
        "q2_mutations": muts,
        "npc_deltas": {},
        "lattice_lines": lattice_lines,
        "lore_shard": None
    }

