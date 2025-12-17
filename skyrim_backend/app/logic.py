from __future__ import annotations

import time
from typing import Any, Dict, Optional


class AttrDict(dict):
    """
    Dict that supports attribute access (a.tags) so old code doesn't explode.
    """
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as e:
            raise AttributeError(k) from e

    def __setattr__(self, k, v):
        self[k] = v


def _wrap_agent(a: Any) -> Any:
    if isinstance(a, dict) and not isinstance(a, AttrDict):
        a = AttrDict(a)
    # ensure common fields exist
    if isinstance(a, dict):
        a.setdefault("tags", [])
        a.setdefault("faction", {})
        a.setdefault("divine", {})
        a.setdefault("daedra", {})
        a.setdefault("trust", 0.5)
        a.setdefault("fear", 0.1)
        a.setdefault("favor", 0.5)
        a.setdefault("gossip_heat", 0.0)
        a.setdefault("last_location", "Unknown")
        a.setdefault("last_seen_ts", float(time.time()))
    return a


def _looks_like_agent_map(m: Any) -> bool:
    if not isinstance(m, dict) or not m:
        return False
    # heuristic: values are dict-ish agents
    sample = next(iter(m.values()))
    return isinstance(sample, (dict, AttrDict))


def _agents_map(world: Any) -> Dict[str, Any]:
    """
    Find the authoritative {name -> agent_state} map from many possible world layouts.
    Supports:
      - dict worlds: world['agents'] / world['npcs'] / world['actors'] or direct map
      - object worlds: world.agents / world.npcs / world.actors
      - nested: world.state.agents, world.world.agents, world.data.agents, etc.
      - last-resort: scan __dict__ for a dict that looks like an agent map
    """
    # 1) world is already a dict
    if isinstance(world, dict):
        for k in ("agents", "npcs", "actors"):
            m = world.get(k)
            if _looks_like_agent_map(m):
                return m
        if _looks_like_agent_map(world):
            return world

    # 2) world has direct attrs
    for k in ("agents", "npcs", "actors"):
        m = getattr(world, k, None)
        if _looks_like_agent_map(m):
            return m

    # 3) nested containers (common patterns)
    for outer in ("state", "world", "data", "ctx", "session"):
        inner = getattr(world, outer, None)
        if inner is None:
            continue
        if isinstance(inner, dict):
            for k in ("agents", "npcs", "actors"):
                m = inner.get(k)
                if _looks_like_agent_map(m):
                    return m
            if _looks_like_agent_map(inner):
                return inner
        else:
            for k in ("agents", "npcs", "actors"):
                m = getattr(inner, k, None)
                if _looks_like_agent_map(m):
                    return m

    # 4) last resort: scan object fields
    d = getattr(world, "__dict__", None)
    if isinstance(d, dict):
        for v in d.values():
            if _looks_like_agent_map(v):
                return v
            if isinstance(v, dict):
                for k in ("agents", "npcs", "actors"):
                    m = v.get(k)
                    if _looks_like_agent_map(m):
                        return m

    raise TypeError(
        f"Unsupported world type: {type(world)} (could not locate agents/npcs/actors map)"
    )


def ensure_agent(world: Any, name: str) -> Any:
    agents = _agents_map(world)
    a = agents.get(name)
    if a is None:
        a = AttrDict(name=name)
        a = _wrap_agent(a)
        agents[name] = dict(a)  # store plain dict for JSON friendliness
        return _wrap_agent(agents[name])
    a = _wrap_agent(a)
    agents[name] = dict(a)
    return _wrap_agent(agents[name])


def get_agent(world: Any, name: str) -> Optional[Any]:
    agents = _agents_map(world)
    a = agents.get(name)
    if a is None:
        return None
    return _wrap_agent(a)


def apply_favor(world: Any, actor: str, channel: str, key: str, delta: float, reason: str = "") -> Any:
    """
    channel: 'divine' | 'daedra' | 'faction' | 'tag' (tag uses key as tag or key ignored)
    """
    a = ensure_agent(world, actor)

    # normalize storage back into the world map at end
    def _commit():
        agents = _agents_map(world)
        agents[actor] = dict(a)

    a.last_seen_ts = float(time.time())

    ch = (channel or "").lower()
    if ch in ("divine", "daedra"):
        m = a.get(ch, {})
        m[key] = float(m.get(key, 0.0)) + float(delta)
        a[ch] = m
        _commit()
        return a

    if ch == "faction":
        m = a.get("faction", {})
        m[key] = float(m.get(key, 0.0)) + float(delta)
        a["faction"] = m
        _commit()
        return a

    if ch == "tag":
        # key is ignored; caller should pass tag via key or handle elsewhere
        _commit()
        return a

    # unknown channel: no-op but don't crash
    _commit()
    return a


def add_tag(world: Any, actor: str, tag: str) -> Any:
    a = ensure_agent(world, actor)
    if tag and tag not in a.tags:
        a.tags.append(tag)
    agents = _agents_map(world)
    agents[actor] = dict(a)
    return a
