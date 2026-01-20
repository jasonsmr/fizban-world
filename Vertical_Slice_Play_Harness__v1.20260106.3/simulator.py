#!/usr/bin/env python3
"""simulator.py (v0.4)

Patch on top of v0.3:
- Supports node-level ws_effects (applied when node is entered)
- Dedupes gain_status in output
- Maps legacy rumor_pressure.none -> xi.faction.local at normalization and load time
- Adds inspect cost (soft): first inspect per node costs +1 tension OR consumes noise_budget flag
  (keeps inspect valuable but no longer always-free)
- Adds 'D' dev view (same as v0.3) with better formatting

Drop-in replacement.
"""

import argparse, json, random, sys, os
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from worldstate_v0_1 import WorldState, apply_mutations as ws_apply_mutations
from render import lattice_voice, lore_voice, derive_attention_heat

from npc_state import NPCStateDB

SAVE_PATH = "./saves"


@dataclass
class PlayerState:
    hp: int = 30
    xp: int = 0
    tokens: int = 2
    status: List[str] = field(default_factory=list)
    inspected_nodes: List[str] = field(default_factory=list)
    ws: WorldState = field(default_factory=lambda: WorldState(seed=0))


def clamp(val, lo, hi):
    return max(lo, min(hi, val))


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, data: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def save_worldstate(save_key: str, ws: WorldState) -> None:
    _ensure_dir(SAVE_PATH)
    _write_json(os.path.join(SAVE_PATH, f"{save_key}.worldstate.json"), ws.to_dict())


def load_worldstate(save_key: str) -> Optional[WorldState]:
    path = os.path.join(SAVE_PATH, f"{save_key}.worldstate.json")
    if not os.path.exists(path):
        return None
    ws = WorldState.from_dict(_read_json(path))
    # sanitize legacy rumor keys if any
    if isinstance(ws.rumor_pressure, dict) and "none" in ws.rumor_pressure:
        ws.rumor_pressure["xi.faction.local"] = ws.rumor_pressure.get("xi.faction.local", ws.rumor_pressure.get("none", 0))
        del ws.rumor_pressure["none"]
    return ws


SCARCITY_MAP = {
    "plentiful": "abundant",
    "stable": "stable",
    "thin": "thin",
    "scarce": "scarce",
    "dire": "critical",
    "abundant": "abundant",
    "critical": "critical",
}


def normalize_q2_mutations(raw_muts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Accepts WS format ({op,path,value}) or legacy ({key,op,value}). Returns WS format."""
    out: List[Dict[str, Any]] = []
    for m in raw_muts or []:
        if not isinstance(m, dict):
            continue
        if "path" in m:
            out.append({"op": m.get("op"), "path": m.get("path"), "value": m.get("value")})
            continue

        key = m.get("key")
        op = m.get("op")
        value = m.get("value")

        if key == "rumor_pressure" and op == "set" and isinstance(value, dict):
            # legacy dict set — map 'none' to local
            v = dict(value)
            if "none" in v:
                v["xi.faction.local"] = v.get("xi.faction.local", v["none"])
                del v["none"]
            # Q2 cap enforcement happens later
            for i, (k, vv) in enumerate(v.items()):
                if i >= 2:
                    break
                try:
                    iv = int(round(float(vv)))
                except Exception:
                    iv = 0
                out.append({"op": "set", "path": f"/rumor_pressure/{k}", "value": iv})
            continue

        if isinstance(key, str) and key.startswith("scarcity_vector.") and op == "set":
            axis = key.split(".", 1)[1]
            mapped = SCARCITY_MAP.get(str(value), "stable")
            out.append({"op": "band_set", "path": f"/scarcity_vector/{axis}", "value": mapped})
            continue

        if key == "tension_index" and op in ("inc", "dec", "set"):
            out.append({"op": op, "path": "/tension_index", "value": int(value)})
            continue

        if isinstance(key, str) and key.startswith("rumor_pressure.") and op in ("inc", "dec", "set"):
            axis = key.split(".", 1)[1]
            if axis == "none":
                axis = "xi.faction.local"
            out.append({"op": op, "path": f"/rumor_pressure/{axis}", "value": int(value)})
            continue
    return out


def apply_ws_mutations(state: PlayerState, muts_ws: List[Dict[str, Any]]) -> None:
    ws_apply_mutations(state.ws, muts_ws)


def load_nodes(path: str):
    nodes = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            nodes[obj["node_id"]] = obj
    return nodes


def block(title: str, body: str):
    print("\n" + "=" * 60)
    print(title)
    print("-" * 60)
    print((body or "").strip())


def status_view(state: PlayerState):
    ws = state.ws
    rp = ws.rumor_pressure
    sv = ws.scarcity_vector
    show_axes = ["water", "food", "medicine", "noise_budget", "memory_clarity", "tools_basic", "fuel"]
    scarcity_lines = []
    for a in show_axes:
        if a in sv:
            scarcity_lines.append(f"  scarcity_vector.{a}: {sv.get(a)}")
    if not scarcity_lines:
        scarcity_lines.append("  scarcity_vector: (none set)")

    heat = derive_attention_heat(ws)

    block(
        "STATUS",
        "\n".join(
            [
                f"HP: {state.hp}/30",
                f"XP: {state.xp}",
                f"Witness-tokens: {state.tokens}",
                f"Status: {', '.join(state.status) if state.status else '(none)'}",
                "",
                "WorldState (WS.v0.1):",
                f"  tension_index: {ws.tension_index}",
                f"  attention_heat (derived): {heat}",
                *scarcity_lines,
                f"  rumor_pressure: {dict(rp)}",
                f"  flags.status: {ws.flags.status}",
                f"  flags.facts: {ws.flags.facts}",
                f"  flags.locks: {ws.flags.locks}",
            ]
        ),
    )


def dev_view(state: PlayerState, last_diff: Optional[Dict[str, Any]]):
    ws = state.ws
    heat = derive_attention_heat(ws)
    rp = sorted((ws.rumor_pressure or {}).items(), key=lambda kv: abs(int(kv[1])) if str(kv[1]).lstrip('-').isdigit() else 0, reverse=True)
    sv = ws.scarcity_vector or {}

    def band_score(b: str) -> int:
        return {"abundant": 0, "stable": 1, "thin": 2, "scarce": 3, "critical": 4}.get(b, 1)

    sv_sorted = sorted(sv.items(), key=lambda kv: band_score(kv[1]), reverse=True)

    lines = []
    lines.append(f"tension_index: {ws.tension_index}")
    lines.append(f"attention_heat: {heat}")
    lines.append("")
    lines.append("rumor_pressure (sorted):")
    for k, v in rp[:12]:
        lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("scarcity_vector (worst first):")
    for k, v in sv_sorted[:12]:
        lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append(f"flags.status: {ws.flags.status}")
    lines.append(f"flags.facts: {ws.flags.facts}")
    lines.append(f"flags.locks: {ws.flags.locks}")
    if last_diff:
        lines.append("")
        lines.append("last turn diff:")
        for k, v in last_diff.items():
            lines.append(f"  {k}: {v}")

    block("DEV", "\n".join(lines))


def _dedupe(seq: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in seq:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def run(nodes, seed: int, save_key: str):
    rng = random.Random(seed)

    state = PlayerState()
    state.ws.seed = seed

    loaded = load_worldstate(save_key)
    if loaded:
        state.ws = loaded
        state.ws.seed = seed
    else:
        state.ws.tension_index = 10
        state.ws.scarcity_vector.setdefault("noise_budget", "stable")
        state.ws.scarcity_vector.setdefault("memory_clarity", "stable")
        state.ws.scarcity_vector.setdefault("tools_basic", "stable")
        state.ws.scarcity_vector.setdefault("water", "stable")
        state.ws.scarcity_vector.setdefault("food", "stable")
        state.ws.rumor_pressure.setdefault("xi.faction.local", 0)

    npcdb = NPCStateDB.load(SAVE_PATH, save_key)

    current = "N001"
    inspected = set()
    visit_counts: Dict[str, int] = {}
    last_diff: Optional[Dict[str, Any]] = None

    while True:
        if current == "END":
            block("RUN COMPLETE", "You step out of the pass with whatever it has taken and whatever it has failed to understand.")
            status_view(state)
            save_worldstate(save_key, state.ws)
            npcdb.save(SAVE_PATH, save_key)
            return

        node = nodes[current]
        visit_counts[current] = visit_counts.get(current, 0) + 1

        # snapshot before
        ws_before = WorldState.from_dict(state.ws.to_dict())

        # apply node-level ws_effects (clocks / relief)
        node_effects = node.get("ws_effects") or []
        if isinstance(node_effects, list) and node_effects:
            apply_ws_mutations(state, node_effects[:2])

        # milestone commit fields -> WS flags
        for f in node.get("facts_add") or []:
            apply_ws_mutations(state, [{"op": "flag_add", "path": "/flags/facts", "value": f}])
        for l in node.get("locks_add") or []:
            apply_ws_mutations(state, [{"op": "flag_add", "path": "/flags/locks", "value": l}])
        for s in node.get("status_add") or []:
            apply_ws_mutations(state, [{"op": "flag_add", "path": "/flags/status", "value": s}])

        # time
        state.ws.time.turn += 1
        state.ws.time.scene_id = f"{node.get('run_id','run')}.{node.get('node_id','node')}"

        title = f"{node['run_id']} / {node['node_id']} — {node['title']}"

        # Anti-monotony: if revisited, shorten the big text.
        revisits = visit_counts[current] - 1
        lore_txt = node.get("lore", "")
        sys_txt = node.get("system", "")
        if revisits >= 1:
            lore_txt = "(Revisit) " + (lore_txt.split("\n")[0] if lore_txt else "")
            sys_txt = "(Revisit) The place feels familiar in the wrong way."
            # small penalty so loops are felt
            apply_ws_mutations(state, [{"op": "inc", "path": "/tension_index", "value": 1}])

        body = [
            "LORE:",
            lore_txt,
            "",
            "SYSTEM:",
            sys_txt,
        ]

        # event beat rendering
        if node.get("event"):
            ev = node["event"]
            body += ["", f"EVENT ({ev.get('kind','event').upper()}):", ev.get("hint", "")] 

        body += [
            "",
            f"(A) {node['choices']['A']['label']} — {node['choices']['A']['desc']}",
            f"(B) {node['choices']['B']['label']} — {node['choices']['B']['desc']}",
            f"(C) {node['choices']['C']['label']} — {node['choices']['C']['desc']}",
            "",
            "Commands: A/B/C choose | I inspect | S status | D dev | H help | Q quit",
        ]
        block(title, "\n".join(body))

        ch = input("Choose: ").strip().upper()
        if ch in ("Q", "QUIT"):
            block("QUIT", "You leave mid-thread. The mountain keeps counting anyway.")
            status_view(state)
            save_worldstate(save_key, state.ws)
            npcdb.save(SAVE_PATH, save_key)
            return
        if ch in ("H", "HELP", "?"):
            with open(os.path.join(os.path.dirname(__file__), "docs", "HELP.md"), "r", encoding="utf-8") as f:
                block("HELP", f.read())
            continue
        if ch in ("S", "STATUS"):
            status_view(state)
            continue
        if ch in ("D", "DEV"):
            dev_view(state, last_diff)
            continue
        if ch in ("I", "INSPECT"):
            if current in inspected:
                block("INSPECT", "You've already combed this place. Any further certainty would be self-deception.")
                continue
            inspected.add(current)
            txt = (node.get("inspect", "") or "").strip() or "You find nothing new—only the same wrongness, patiently repeating."

            # inspect no longer free: small tension bump (or later: consume noise_budget)
            apply_ws_mutations(state, [{"op": "inc", "path": "/tension_index", "value": 1}])

            state.xp += 2
            if rng.random() < 0.10:
                state.tokens += 1
                txt += "\n\nSYSTEM BONUS: +1 witness-token."
            else:
                txt += "\n\nSYSTEM BONUS: +2 XP."
            block("INSPECT", txt)
            save_worldstate(save_key, state.ws)
            npcdb.save(SAVE_PATH, save_key)
            continue
        if ch not in ("A", "B", "C"):
            print("Invalid choice.")
            continue

        effects = node["choices"][ch].get("effects") or {}
        cost = int(effects.get("cost_token", 0) or 0)
        if cost:
            if state.tokens < cost:
                block("RESULT (SYSTEM)", "You reach for a token and find none. The pass hears the lie.\nNo action taken. (Tension +2)")
                apply_ws_mutations(state, [{"op": "inc", "path": "/tension_index", "value": 2}])
                save_worldstate(save_key, state.ws)
                npcdb.save(SAVE_PATH, save_key)
                continue
            state.tokens -= cost

        # base stats
        state.xp += int(effects.get("xp", 0) or 0)
        state.hp = clamp(state.hp + int(effects.get("hp", 0) or 0), 0, 30)

        gain_status = _dedupe(list(effects.get("gain_status", []) or []))
        for st in gain_status:
            if st not in state.status:
                state.status.append(st)

        # choice-level ws_effects preferred
        muts_ws: List[Dict[str, Any]] = []
        if isinstance(effects.get("ws_effects"), list):
            muts_ws = list(effects.get("ws_effects") or [])
        else:
            muts_ws = normalize_q2_mutations(effects.get("q2_mutations", []) or [])

        apply_ws_mutations(state, muts_ws)

        # update NPC minimal state (one default npc per scene for now)
        npcdb.observe_world("npc.local.watcher", state.ws)

        ws_after = WorldState.from_dict(state.ws.to_dict())

        # diff summary
        last_diff = {
            "tension": f"{ws_before.tension_index}→{ws_after.tension_index}",
            "heat": f"{derive_attention_heat(ws_before)}→{derive_attention_heat(ws_after)}",
        }

        lines = [
            f"You chose {ch}.",
            f"XP +{effects.get('xp',0)} | HP {int(effects.get('hp',0) or 0):+d} | Tokens -{cost}",
            f"Status gained: {', '.join(gain_status) or '(none)'}",
            "",
            "Worldstate changes (≤2):",
        ] + [f"- {m.get('op')} {m.get('path')} {m.get('value')}" for m in (muts_ws or [])]
        block("RESULT (SYSTEM)", "\n".join(lines))

        print("\n[Lattice]")
        choice_obj = {
            "id": ch,
            "label": node["choices"][ch].get("label", ch),
            "text": node["choices"][ch].get("desc", ""),
        }
        print(lattice_voice(choice_obj, muts_ws, ws_before, ws_after))

        shard = lore_voice(ws_before, ws_after)
        if shard:
            print("\n[Lore]")
            print(shard)

        if state.hp <= 0:
            block("FAIL STATE", "Your body stops cooperating. The mountain does not care why.")
            status_view(state)
            save_worldstate(save_key, state.ws)
            npcdb.save(SAVE_PATH, save_key)
            return

        save_worldstate(save_key, state.ws)
        npcdb.save(SAVE_PATH, save_key)
        current = node["choices"][ch]["next"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--seed", type=int, default=401)
    ap.add_argument("--save", default=None)
    a = ap.parse_args()

    save_key = a.save or f"{a.run}_{a.seed}"
    path = os.path.join(os.path.dirname(__file__), "campaigns", f"{a.run}.scene_nodes.jsonl")
    if not os.path.exists(path):
        print(f"Missing campaign file: {path}", file=sys.stderr)
        sys.exit(2)
    nodes = load_nodes(path)
    run(nodes, a.seed, save_key)


if __name__ == "__main__":
    main()
