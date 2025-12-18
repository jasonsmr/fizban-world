from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .compat import (
    ensure_dict_field,
    find_first_mapping_field,
    get_attr_or_key,
    model_to_dict,
    now_ts,
)


class AttrDict(dict):
    """dict with attribute access (a.tags == a['tags'])."""
    def __getattr__(self, k: str) -> Any:
        try:
            return self[k]
        except KeyError as e:
            raise AttributeError(k) from e

    def __setattr__(self, k: str, v: Any) -> None:
        self[k] = v


_AGENT_MAP_CANDIDATES = (
    "agents",
    "npcs",
    "actors",
    "characters",
    "people",
    "entities",
)

# If your WorldState stores nested structures, we can extend this later:
_NESTED_CONTAINER_CANDIDATES = (
    "state",
    "world",
    "data",
    "store",
)


def _coerce_agent_obj(x: Any) -> AttrDict:
    if isinstance(x, AttrDict):
        return x
    if isinstance(x, dict):
        return AttrDict(x)
    # pydantic/dataclass/object
    d = model_to_dict(x)
    if isinstance(d, dict):
        return AttrDict(d)
    return AttrDict({"value": d})


def _default_agent(name: str) -> AttrDict:
    return AttrDict({
        "name": name,
        "trust": 0.5,
        "fear": 0.1,
        "favor": 0.5,
        "gossip_heat": 0.0,
        "last_location": "Unknown",
        "last_seen_ts": now_ts(),
        "tags": [],
        "faction": {},
        "divine": {},
        "daedra": {},
    })


def _find_agents_map(world: Any) -> Tuple[Dict[str, Any], str]:
    """
    Returns (agents_map, where_string).
    Supports:
      - world as dict
      - world with .agents/.npcs/.actors...
      - world with nested container (world.state.agents, etc) [basic]
    """
    if world is None:
        raise TypeError("world is None")

    # Direct mapping world
    if isinstance(world, dict):
        hit = find_first_mapping_field(world, _AGENT_MAP_CANDIDATES)
        if hit:
            k, m = hit
            # write back to keep it a real dict
            world[k] = m
            return world[k], f"world['{k}']"
        raise TypeError("Unsupported world dict: could not locate agents/npcs/actors map")

    # Direct attribute
    hit = find_first_mapping_field(world, _AGENT_MAP_CANDIDATES)
    if hit:
        k, m = hit
        # ensure it's a real dict stored on the object
        stored = ensure_dict_field(world, k)
        stored.clear()
        stored.update(m)
        return stored, f"world.{k}"

    # Nested container (one level)
    for container_name in _NESTED_CONTAINER_CANDIDATES:
        container = get_attr_or_key(world, container_name, None)
        if container is None:
            continue
        # recurse one level only (keeps behavior predictable)
        if isinstance(container, dict):
            hit2 = find_first_mapping_field(container, _AGENT_MAP_CANDIDATES)
            if hit2:
                k2, m2 = hit2
                container[k2] = dict(m2)
                return container[k2], f"world.{container_name}['{k2}']"
        else:
            hit2 = find_first_mapping_field(container, _AGENT_MAP_CANDIDATES)
            if hit2:
                k2, m2 = hit2
                stored2 = ensure_dict_field(container, k2)
                stored2.clear()
                stored2.update(m2)
                return stored2, f"world.{container_name}.{k2}"

    raise TypeError(f"Unsupported world type: {type(world)} (could not locate agents/npcs/actors map)")


def list_agents(world: Any) -> List[str]:
    agents, _where = _find_agents_map(world)
    return sorted(list(agents.keys()))


def ensure_agent(world: Any, name: str, seed: Optional[Dict[str, Any]] = None) -> AttrDict:
    agents, _where = _find_agents_map(world)
    if name not in agents:
        agents[name] = dict(seed) if seed else dict(_default_agent(name))
    a = _coerce_agent_obj(agents[name])
    # write back coerced dict so next call is stable
    agents[name] = dict(a)

    # normalize common fields to avoid future breakage
    if "name" not in agents[name]:
        agents[name]["name"] = name
    if not isinstance(agents[name].get("tags", []), list):
        agents[name]["tags"] = list(agents[name].get("tags") or [])
    for bucket in ("faction", "divine", "daedra"):
        if not isinstance(agents[name].get(bucket, {}), dict):
            agents[name][bucket] = dict(agents[name].get(bucket) or {})

    return _coerce_agent_obj(agents[name])


def get_agent(world: Any, name: str) -> AttrDict:
    return ensure_agent(world, name)


@dataclass
class AppliedEffect:
    channel: str
    key: Optional[str]
    delta: float
    tag: Optional[str]
    note: Optional[str]


def apply_effect(agent: AttrDict, eff: Dict[str, Any]) -> AppliedEffect:
    ch = str(eff.get("channel") or "")
    key = eff.get("key")
    tag = eff.get("tag")
    note = eff.get("note")
    try:
        delta = float(eff.get("delta", 0.0))
    except Exception:
        delta = 0.0

    if ch == "tag":
        if tag:
            if tag not in agent.tags:
                agent.tags.append(tag)
        return AppliedEffect(channel="tag", key=None, delta=delta, tag=tag, note=note)

    if ch in ("divine", "daedra", "faction"):
        bucket = agent.get(ch, {})
        if not isinstance(bucket, dict):
            bucket = {}
            agent[ch] = bucket
        if key:
            bucket[key] = float(bucket.get(key, 0.0)) + delta
        return AppliedEffect(channel=ch, key=key, delta=delta, tag=None, note=note)

    # unknown channel: no-op but report it
    return AppliedEffect(channel=ch, key=key, delta=delta, tag=tag, note=note)


def apply_realm_selection(
    world: Any,
    actor: str,
    selection_id: str,
    location: str,
    effects: List[Dict[str, Any]],
    tags: List[str],
) -> Tuple[List[AppliedEffect], int]:
    a = ensure_agent(world, actor)
    if location:
        a["last_location"] = location
    a["last_seen_ts"] = now_ts()

    # apply request tags (top-level)
    for t in tags or []:
        if t and t not in a.tags:
            a.tags.append(t)

    applied: List[AppliedEffect] = []
    for eff in effects or []:
        applied.append(apply_effect(a, eff))

    # bump tick if present; if absent, keep 0 but don't crash
    tick = get_attr_or_key(world, "tick", 0)
    try:
        tick_i = int(tick)
    except Exception:
        tick_i = 0
    return applied, tick_i

