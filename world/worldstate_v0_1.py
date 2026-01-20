# worldstate_v0_1.py
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional

SCARCITY_BANDS = ["abundant", "stable", "thin", "scarce", "critical"]
SCARCITY_INDEX = {b:i for i,b in enumerate(SCARCITY_BANDS)}

def _clamp_int(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))

@dataclass
class TimeState:
    turn: int = 0
    visit_id: str = "visit_0000"
    scene_id: str = "scene.unknown"

@dataclass
class FlagState:
    status: List[str] = field(default_factory=list)
    facts: List[str] = field(default_factory=list)
    locks: List[str] = field(default_factory=list)

@dataclass
class WorldState:
    schema: str = "fizban.worldstate.v0.1"
    seed: int = 0
    time: TimeState = field(default_factory=TimeState)

    tension_index: int = 0
    scarcity_vector: Dict[str, str] = field(default_factory=dict)
    rumor_pressure: Dict[str, int] = field(default_factory=dict)

    flags: FlagState = field(default_factory=FlagState)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "WorldState":
        ws = WorldState()
        ws.schema = d.get("schema", ws.schema)
        ws.seed = int(d.get("seed", 0))
        t = d.get("time", {}) or {}
        ws.time = TimeState(
            turn=int(t.get("turn", 0)),
            visit_id=str(t.get("visit_id", "visit_0000")),
            scene_id=str(t.get("scene_id", "scene.unknown")),
        )
        ws.tension_index = int(d.get("tension_index", 0))
        ws.scarcity_vector = dict(d.get("scarcity_vector", {}) or {})
        ws.rumor_pressure = {k:int(v) for k,v in (d.get("rumor_pressure", {}) or {}).items()}
        f = d.get("flags", {}) or {}
        ws.flags = FlagState(
            status=list(f.get("status", []) or []),
            facts=list(f.get("facts", []) or []),
            locks=list(f.get("locks", []) or []),
        )
        validate_and_clamp(ws)
        return ws

def validate_and_clamp(ws: WorldState) -> None:
    if ws.schema != "fizban.worldstate.v0.1":
        # allow forward compatibility, but don't silently accept junk
        ws.schema = "fizban.worldstate.v0.1"

    ws.tension_index = _clamp_int(ws.tension_index, 0, 100)

    # scarcity bands
    for k, v in list(ws.scarcity_vector.items()):
        if v not in SCARCITY_INDEX:
            ws.scarcity_vector[k] = "stable"

    # rumor pressure
    for k, v in list(ws.rumor_pressure.items()):
        ws.rumor_pressure[k] = _clamp_int(int(v), -5, 5)

    # de-dup flags
    ws.flags.status = sorted(set(ws.flags.status))
    ws.flags.facts  = sorted(set(ws.flags.facts))
    ws.flags.locks  = sorted(set(ws.flags.locks))

def _band_shift(current: str, delta: int) -> str:
    i = SCARCITY_INDEX.get(current, SCARCITY_INDEX["stable"])
    i2 = _clamp_int(i + int(delta), 0, len(SCARCITY_BANDS)-1)
    return SCARCITY_BANDS[i2]

def apply_mutations(ws: WorldState, mutations: List[Dict[str, Any]]) -> None:
    # Q2 cap: <=2 per beat
    if len(mutations) > 2:
        raise ValueError(f"Q2 mutation cap exceeded: {len(mutations)} > 2")

    for m in mutations:
        op = m.get("op")
        path = m.get("path")
        value = m.get("value")

        if not isinstance(path, str) or not path.startswith("/"):
            raise ValueError(f"Invalid mutation path: {path}")

        # tension
        if path == "/tension_index":
            if op == "set":
                ws.tension_index = int(value)
            elif op == "inc":
                ws.tension_index += int(value)
            elif op == "dec":
                ws.tension_index -= int(value)
            else:
                raise ValueError(f"Bad op for tension_index: {op}")

        # rumor_pressure entries
        elif path.startswith("/rumor_pressure/"):
            key = path.split("/", 2)[2]
            ws.rumor_pressure.setdefault(key, 0)
            if op == "set":
                ws.rumor_pressure[key] = int(value)
            elif op == "inc":
                ws.rumor_pressure[key] += int(value)
            elif op == "dec":
                ws.rumor_pressure[key] -= int(value)
            else:
                raise ValueError(f"Bad op for rumor_pressure: {op}")

        # scarcity entries
        elif path.startswith("/scarcity_vector/"):
            key = path.split("/", 2)[2]
            cur = ws.scarcity_vector.get(key, "stable")
            if op == "band_set":
                if value not in SCARCITY_INDEX:
                    raise ValueError(f"Bad scarcity band: {value}")
                ws.scarcity_vector[key] = value
            elif op == "band_shift":
                ws.scarcity_vector[key] = _band_shift(cur, int(value))
            else:
                raise ValueError(f"Bad op for scarcity_vector: {op}")

        # flags lists
        elif path in ("/flags/status", "/flags/facts", "/flags/locks"):
            bucket = path.split("/")[-1]  # status/facts/locks
            token = str(value)
            lst = getattr(ws.flags, bucket)
            if op == "flag_add":
                if token not in lst:
                    lst.append(token)
            elif op == "flag_remove":
                if token in lst:
                    lst.remove(token)
            else:
                raise ValueError(f"Bad op for flags: {op}")

        else:
            raise ValueError(f"Unknown mutation path: {path}")

    validate_and_clamp(ws)

