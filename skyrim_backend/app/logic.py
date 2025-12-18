from __future__ import annotations

from typing import Any, Dict, Iterable, MutableMapping, Optional, Tuple

from app.compat import find_agents_map


def _as_attrdict(d: Dict[str, Any]) -> Any:
    """
    Minimal object wrapper so old code can do a.tags / a.faction etc.
    Keeps state mutable and JSON-friendly.
    """
    class AttrDict(dict):
        __getattr__ = dict.get
        def __setattr__(self, k, v): self[k] = v

    return AttrDict(d)


def ensure_agent(world: Any, name: str) -> Any:
    agents, _where = find_agents_map(world)

    if name in agents:
        a = agents[name]
        # normalize dict -> attrdict
        if isinstance(a, dict) and not hasattr(a, "tags"):
            agents[name] = _as_attrdict(a)
        return agents[name]

    # default skeleton
    agents[name] = _as_attrdict(
        {
            "name": name,
            "trust": 0.5,
            "fear": 0.1,
            "favor": 0.5,
            "gossip_heat": 0.0,
            "last_location": "Unknown",
            "last_seen_ts": 0.0,
            "tags": [],
            "faction": {},
            "divine": {},
            "daedra": {},
        }
    )
    return agents[name]


def get_agent(world: Any, name: str) -> Any:
    agents, _where = find_agents_map(world)
    if name in agents:
        a = agents[name]
        if isinstance(a, dict) and not hasattr(a, "tags"):
            agents[name] = _as_attrdict(a)
        return agents[name]
    return ensure_agent(world, name)


def ensure_tags(agent: Any, tags: Iterable[str]) -> None:
    if not hasattr(agent, "tags") or agent.tags is None:
        agent.tags = []
    for t in tags:
        if t not in agent.tags:
            agent.tags.append(t)


def set_last_location(agent: Any, location: str) -> None:
    agent.last_location = location


def _bucket(agent: Any, channel: str) -> MutableMapping[str, float]:
    # Ensure channel maps exist and are dict-like
    if channel not in ("faction", "divine", "daedra"):
        # For unknown channels, store under agent[channel] map
        if not hasattr(agent, channel) or getattr(agent, channel) is None:
            setattr(agent, channel, {})
        b = getattr(agent, channel)
        if isinstance(b, dict):
            return b
        # last resort: replace
        setattr(agent, channel, {})
        return getattr(agent, channel)

    if not hasattr(agent, channel) or getattr(agent, channel) is None:
        setattr(agent, channel, {})
    b = getattr(agent, channel)
    if isinstance(b, dict):
        return b
    setattr(agent, channel, {})
    return getattr(agent, channel)


def apply_effect(agent: Any, eff: Dict[str, Any]) -> None:
    """
    eff format:
      {channel, key?, tag?, delta, note?}
    """
    channel = (eff.get("channel") or "").strip()
    delta = float(eff.get("delta") or 0.0)

    if channel == "tag":
        tag = eff.get("tag")
        if tag:
            ensure_tags(agent, [tag])
        return

    key = eff.get("key")
    if not key:
        return

    b = _bucket(agent, channel)
    b[key] = float(b.get(key, 0.0) + delta)
