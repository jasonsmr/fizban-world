#!/usr/bin/env python3
import argparse, json, random, sys, os
from dataclasses import dataclass, field
from typing import Dict, List, Any

@dataclass
class PlayerState:
    hp: int = 30
    xp: int = 0
    tokens: int = 2
    status: List[str] = field(default_factory=list)
    clues: List[str] = field(default_factory=list)
    inspected_nodes: List[str] = field(default_factory=list)
    worldstate: Dict[str, Any] = field(default_factory=lambda: {
        "tension_index": 10,
        "scarcity_vector": {"labor": "stable"},
        "rumor_pressure": {"none": 0.10},
    })

def clamp(val, lo, hi): return max(lo, min(hi, val))


STATUS_INFO = {
    "ROUTE_MARKED": "You left navigational marks others won't notice. Safer returns, less wandering.",
    "WITNESS_LEFT": "You paid the place with a trace of yourself. Easier passage now, easier to be found later.",
    "STRAINED": "You pushed too hard. Until you rest, risky moves will feel worse.",
    "CLUE_CHALK_SIGIL": "A chalk sigil that steadies timing for a minute if you keep moving.",
    "CLUE_NINTH_BEAT": "A learned trick: adding a ninth beat can break the spire's pull.",
    "CLUE_ASH_BOUNDARY": "Proof: wind boundaries act like invisible panes; they align to stone, not gusts.",
    "CLUE_COUNT_SHIFT": "Counting aloud accelerates number-shift. Silence slows it.",
    "CLUE_FORTY_SECONDS": "Rime grows in forty-second pulses. Time your grabs accordingly.",
}


def apply_mutations(state: PlayerState, muts: List[Dict[str, Any]]):
    for m in muts:
        key, op, value = m["key"], m["op"], m["value"]
        if key == "tension_index":
            if op == "inc": state.worldstate["tension_index"] = clamp(state.worldstate["tension_index"] + int(value), 0, 100)
            elif op == "dec": state.worldstate["tension_index"] = clamp(state.worldstate["tension_index"] - int(value), 0, 100)
            elif op == "set": state.worldstate["tension_index"] = clamp(int(value), 0, 100)
        elif key.startswith("scarcity_vector."):
            axis = key.split(".", 1)[1]
            if op == "set" and value in ("plentiful","stable","scarce","dire"):
                state.worldstate.setdefault("scarcity_vector", {})[axis] = value
        elif key == "rumor_pressure":
            if op == "set" and isinstance(value, dict):
                rp = state.worldstate.setdefault("rumor_pressure", {})
                for k,v in value.items():
                    try: rp[k] = float(v)
                    except Exception: pass

def load_nodes(path: str):
    nodes = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            obj = json.loads(line)
            nodes[obj["node_id"]] = obj
    return nodes

def block(title: str, body: str):
    print("\n" + "="*60)
    print(title)
    print("-"*60)
    print((body or "").strip())

def status_view(state: PlayerState):
    rp = state.worldstate.get("rumor_pressure", {})
    sv = state.worldstate.get("scarcity_vector", {})
    block("STATUS", "\n".join([
        f"HP: {state.hp}/30",
        f"XP: {state.xp}",
        f"Witness-tokens: {state.tokens}",
        f"Status: {', '.join(state.status) if state.status else '(none)'}",
        "",
        "Worldstate (local test model):",
        f"  tension_index: {state.worldstate.get('tension_index')}",
        f"  scarcity_vector.labor: {sv.get('labor','stable')}",
        f"  rumor_pressure: {rp}",
    ]))

def run(nodes, seed: int):
    rng = random.Random(seed)
    state = PlayerState()
    current = "N001"
    inspected = set()

    while True:
        if current == "END":
            block("RUN COMPLETE", "You step out of the pass with whatever it has taken and whatever it has failed to understand.")
            status_view(state); return

        node = nodes[current]
        title = f"{node['run_id']} / {node['node_id']} — {node['title']}"
        body = [
            "LORE:",
            node.get("lore",""),
            "",
            "SYSTEM:",
            node.get("system",""),
            "",
            f"(A) {node['choices']['A']['label']} — {node['choices']['A']['desc']}",
            f"(B) {node['choices']['B']['label']} — {node['choices']['B']['desc']}",
            f"(C) {node['choices']['C']['label']} — {node['choices']['C']['desc']}",
            "",
            "Commands: A/B/C choose | I inspect | S status | H help | Q quit"
        ]
        block(title, "\n".join(body))

        ch = input("Choose: ").strip().upper()
        if ch in ("Q","QUIT"):
            block("QUIT", "You leave mid-thread. The mountain keeps counting anyway.")
            status_view(state); return
        if ch in ("H","HELP","?"):
            with open(os.path.join(os.path.dirname(__file__), "docs", "HELP.md"), "r", encoding="utf-8") as f:
                block("HELP", f.read()); continue
        if ch in ("S","STATUS"):
            status_view(state); continue
        if ch in ("I","INSPECT"):
            if current in inspected:
                block("INSPECT", "You've already combed this place. Any further certainty would be self-deception.")
                continue
            inspected.add(current)
            txt = (node.get("inspect","") or "").strip() or "You find nothing new—only the same wrongness, patiently repeating."
            state.xp += 2
            if rng.random() < 0.10:
                state.tokens += 1
                txt += "\n\nSYSTEM BONUS: +1 witness-token."
            else:
                txt += "\n\nSYSTEM BONUS: +2 XP."
            block("INSPECT", txt)
            continue
        if ch not in ("A","B","C"):
            print("Invalid choice."); continue

        effects = node["choices"][ch]["effects"]
        cost = int(effects.get("cost_token",0))
        if cost:
            if state.tokens < cost:
                block("RESULT (SYSTEM)", "You reach for a token and find none. The pass hears the lie.\nNo action taken. (Tension +2)")
                state.worldstate["tension_index"] = clamp(state.worldstate["tension_index"] + 2, 0, 100)
                continue
            state.tokens -= cost

        state.xp += int(effects.get("xp",0))
        state.hp = clamp(state.hp + int(effects.get("hp",0)), 0, 30)
        for st in effects.get("gain_status",[]) or []:
            if st not in state.status: state.status.append(st)

        muts = effects.get("q2_mutations",[]) or []
        apply_mutations(state, muts)

        lines = [
            f"You chose {ch}.",
            f"XP +{effects.get('xp',0)} | HP {int(effects.get('hp',0)):+d} | Tokens -{cost}",
            f"Status gained: {', '.join(effects.get('gain_status',[]) or []) or '(none)'}",
            "",
            "Worldstate changes (≤2):"
        ] + [f"- {m['key']} {m['op']} {m['value']}" for m in muts]
        block("RESULT (SYSTEM)", "\n".join(lines))

        if state.hp <= 0:
            block("FAIL STATE", "Your body stops cooperating. The mountain does not care why.")
            status_view(state); return

        current = node["choices"][ch]["next"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--seed", type=int, default=401)
    a = ap.parse_args()
    path = os.path.join(os.path.dirname(__file__), "campaigns", f"{a.run}.scene_nodes.jsonl")
    if not os.path.exists(path):
        print(f"Missing campaign file: {path}", file=sys.stderr); sys.exit(2)
    nodes = load_nodes(path)
    run(nodes, a.seed)

if __name__ == "__main__":
    main()
