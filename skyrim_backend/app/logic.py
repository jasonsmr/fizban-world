from __future__ import annotations

from typing import Any, Dict, Iterable, List, MutableMapping, Optional, Tuple

from .compat import (
    bump_tick,
    ensure_dict_field,
    ensure_list_field,
    get_attr_or_key,
    now_ts,
    set_attr_or_key,
)


# -----------------------------
# Agents container discovery
# -----------------------------
_AGENT_FIELD_CANDIDATES = ("agents", "npcs", "characters")


def _is_mutable_mapping(x: Any) -> bool:
    try:
        return isinstance(x, MutableMapping)
    except Exception:
        return False


def _as_agent_dict(x: Any) -> Dict[str, Any]:
    """
    Normalize a single "agent" representation into a dict.
    Accepts:
      - dict-like
      - string (name)
      - object with .name or mapping key "name"
    """
    if x is None:
        return {"name": "Unknown"}
    if isinstance(x, dict):
        return dict(x)
    if isinstance(x, str):
        return {"name": x}
    name = get_attr_or_key(x, "name", None)
    if isinstance(name, str) and name:
        # try a shallow vars() dump if possible
        try:
            d = dict(vars(x))
            d.setdefault("name", name)
            return d
        except Exception:
            return {"name": name}
    # fallback
    return {"name": "Unknown"}


def _normalize_agents_value(world: Any, field_name: str, value: Any) -> Dict[str, Dict[str, Any]]:
    """
    Convert whatever world.<field_name> is into a dict: {name: agent_dict}.
    If possible, write it back into the world so future reads are stable.
    """
    # Case 1: already a mapping {name: agent}
    if isinstance(value, dict):
        out: Dict[str, Dict[str, Any]] = {}
        for k, v in value.items():
            nm = str(k)
            out[nm] = _as_agent_dict(v)
            out[nm].setdefault("name", nm)
        # persist normalized dict
        set_attr_or_key(world, field_name, out)
        return out

    if _is_mutable_mapping(value):
        # mutable mapping but not a plain dict; normalize to dict and persist
        out2: Dict[str, Dict[str, Any]] = {}
        try:
            for k, v in value.items():  # type: ignore[attr-defined]
                nm = str(k)
                out2[nm] = _as_agent_dict(v)
                out2[nm].setdefault("name", nm)
        except Exception:
            out2 = {}
        set_attr_or_key(world, field_name, out2)
        return out2

    # Case 2: list/tuple/etc
    if isinstance(value, (list, tuple)):
        out3: Dict[str, Dict[str, Any]] = {}
        for item in value:
            ad = _as_agent_dict(item)
            nm = str(ad.get("name") or "Unknown")
            if not nm or nm == "Unknown":
                # skip nameless entries
                continue
            out3[nm] = ad
        # persist normalized dict
        set_attr_or_key(world, field_name, out3)
        return out3

    # Case 3: missing / unknown type -> empty dict
    out4: Dict[str, Dict[str, Any]] = {}
    set_attr_or_key(world, field_name, out4)
    return out4


def _find_agents_map(world: Any) -> Tuple[Dict[str, Dict[str, Any]], str]:
    """
    Return (agents_dict, where_string).
    This function NEVER returns a non-dict agents container.
    """
    # Try known fields
    for fname in _AGENT_FIELD_CANDIDATES:
        val = get_attr_or_key(world, fname, None)
        if val is None:
            continue

        # Accept dict/mapping/list/tuple; normalize all of them
        if isinstance(val, (dict, list, tuple)) or _is_mutable_mapping(val):
            agents = _normalize_agents_value(world, fname, val)
            return agents, f"world.{fname}"

    # If nothing found, create world.agents
    agents = _normalize_agents_value(world, "agents", None)
    return agents, "world.agents(created)"


# -----------------------------
# Agent shape helpers
# -----------------------------
def _ensure_agent_shape(agent: Dict[str, Any]) -> Dict[str, Any]:
    agent.setdefault("name", "Unknown")
    agent.setdefault("trust", 0.5)
    agent.setdefault("fear", 0.1)
    agent.setdefault("favor", 0.5)
    agent.setdefault("gossip_heat", 0.0)
    agent.setdefault("last_location", "Unknown")
    agent.setdefault("last_seen_ts", now_ts())

    # containers
    if not isinstance(agent.get("tags"), list):
        agent["tags"] = []
    for ch in ("faction", "divine", "daedra"):
        if not isinstance(agent.get(ch), dict):
            agent[ch] = {}
    return agent


def list_agents(world: Any) -> List[str]:
    agents, _where = _find_agents_map(world)
    return sorted(list(agents.keys()))


def get_agent(world: Any, name: str) -> Dict[str, Any]:
    agents, _where = _find_agents_map(world)
    if name not in agents or not isinstance(agents.get(name), dict):
        agents[name] = _ensure_agent_shape({"name": name})
    else:
        agents[name] = _ensure_agent_shape(agents[name])
    # touch "last seen"
    agents[name]["last_seen_ts"] = now_ts()
    return agents[name]


# -----------------------------
# Realm selection application
# -----------------------------
def _apply_effect(agent: Dict[str, Any], eff: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Apply a single effect dict to an agent.
    Returns a normalized applied-effect payload (for API output), or None to skip.
    """
    channel = str(eff.get("channel") or "").strip()
    key = eff.get("key", None)
    tag = eff.get("tag", None)
    note = eff.get("note", None)

    try:
        delta = float(eff.get("delta", 0.0) or 0.0)
    except Exception:
        delta = 0.0

    if not channel:
        return None

    # tag channel -> add tag string to tags list
    if channel == "tag":
        t = str(tag or eff.get("key") or "").strip()
        if t:
            if t not in agent["tags"]:
                agent["tags"].append(t)
        return {"channel": "tag", "key": None, "delta": 0.0, "tag": t or None, "note": note}

    # other channels -> numeric accumulators in dict fields
    if channel not in ("faction", "divine", "daedra"):
        # unknown channel; ignore but report
        return {"channel": channel, "key": str(key) if key is not None else None, "delta": delta, "tag": None, "note": note}

    if key is None:
        return None

    k = str(key)
    bucket = agent[channel]
    try:
        cur = float(bucket.get(k, 0.0) or 0.0)
    except Exception:
        cur = 0.0
    bucket[k] = cur + delta
    return {"channel": channel, "key": k, "delta": delta, "tag": None, "note": note}


def apply_realm_selection(
    world: Any,
    actor: str,
    selection_id: str,
    location: str,
    effects: Optional[List[Dict[str, Any]]] = None,
    tags: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Core application of a "realm selection" event.
    Returns (applied_effects, tick_int).
    """
    a = get_agent(world, actor)
    a["last_location"] = str(location or a.get("last_location") or "Unknown")
    a["last_seen_ts"] = now_ts()

    # attach any request tags
    if tags:
        for t in tags:
            ts = str(t).strip()
            if ts and ts not in a["tags"]:
                a["tags"].append(ts)

    applied: List[Dict[str, Any]] = []
    if effects:
        for e in effects:
            if not isinstance(e, dict):
                continue
            out = _apply_effect(a, e)
            if out is not None:
                applied.append(out)

    tick = bump_tick(world, 1)
    return applied, tick
