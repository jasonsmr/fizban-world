from __future__ import annotations

import time
from typing import Any, Dict, Optional


class AttrDict(dict):
    """
    dict that also supports attribute access:
      a["tags"] <-> a.tags
    """
    def __getattr__(self, k: str):
        try:
            return self[k]
        except KeyError as e:
            raise AttributeError(k) from e

    def __setattr__(self, k: str, v):
        self[k] = v


def _now() -> float:
    return time.time()


def _agents_map(world: Any) -> Dict[str, Any]:
    # Supports both: world.agents or world["agents"]
    if hasattr(world, "agents"):
        m = getattr(world, "agents")
        if m is None:
            m = {}
            setattr(world, "agents", m)
        return m
    if isinstance(world, dict):
        world.setdefault("agents", {})
        return world["agents"]
    raise TypeError(f"Unsupported world type: {type(world)}")


def _to_attrdict(x: Any) -> AttrDict:
    if isinstance(x, AttrDict):
        return x
    if isinstance(x, dict):
        return AttrDict(x)
    # last resort: object -> dict-ish
    return AttrDict({"value": x})


def _default_agent(name: str) -> AttrDict:
    return AttrDict({
        "name": name,
        "trust": 0.5,
        "fear": 0.1,
        "favor": 0.5,
        "gossip_heat": 0.0,
        "last_location": "Unknown",
        "last_seen_ts": _now(),
        "tags": [],
        "faction": {},
        "divine": {},
        "daedra": {},
    })


def ensure_agent(world: Any, name: str) -> AttrDict:
    agents = _agents_map(world)
    a = agents.get(name)
    if a is None:
        a = _default_agent(name)
        agents[name] = a
        return a
    # normalize stored type to AttrDict so a.tags works everywhere
    a2 = _to_attrdict(a)
    agents[name] = a2
    return a2


def get_agent(world: Any, name: str) -> AttrDict:
    # hard guarantee: always returns AttrDict with .tags available
    return ensure_agent(world, name)


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def apply_favor(world: Any, actor: str, channel: str, key: Optional[str], delta: float, reason: str = "") -> AttrDict:
    """
    Compatibility target:
      apply_favor(WORLD, "Player", "divine", "Akatosh", 0.10, "start_shrine")
      apply_favor(WORLD, "Player", "faction", "Companions", 0.05, "start_affinity")
      apply_favor(WORLD, "Player", "daedra", "Boethiah", -0.05, "insulted")
      apply_favor(WORLD, "Player", "tag", "alternate_start", 0.0, "flag")  # key used if tag missing
    """
    a = ensure_agent(world, actor)
    a["last_seen_ts"] = _now()

    ch = (channel or "").strip().lower()

    if ch == "tag":
        tag = key or ""
        if tag and tag not in a["tags"]:
            a["tags"].append(tag)
        return a

    if ch == "divine":
        if not key:
            return a
        cur = float(a["divine"].get(key, 0.0))
        a["divine"][key] = _clamp01(cur + float(delta))
        return a

    if ch == "daedra":
        if not key:
            return a
        cur = float(a["daedra"].get(key, 0.0))
        a["daedra"][key] = _clamp01(cur + float(delta))
        return a

    if ch == "faction":
        if not key:
            return a
        cur = float(a["faction"].get(key, 0.0))
        a["faction"][key] = _clamp01(cur + float(delta))
        return a

    # unknown channel: no-op but keep server stable
    return a
