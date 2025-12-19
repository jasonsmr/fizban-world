# app/travel.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from .compat import (
    bump_tick,
    now_ts,
    get_attr_or_key,
    world_get_meta,
    world_set_meta,
)

# ----------------------------
# Meta keys (world.meta)
# ----------------------------
META_ACTOR_LOCS = "actor_locations"  # Dict[str, str]
META_TRAVEL_LOG = "travel_log"       # List[dict]

# Legacy per-actor meta keys (backwards compatible)
LEGACY_LAST_LOC_KEY = "travel:last_location:{actor}"
LEGACY_LAST_SEEN_KEY = "travel:last_seen_ts:{actor}"


@dataclass
class TravelOption:
    to_location: str
    lane: Optional[str] = None
    title: str = ""
    desc: str = ""
    tags: Optional[List[str]] = None
    cost: int = 0
    provider: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "to_location": self.to_location,
            "lane": self.lane,
            "title": self.title,
            "desc": self.desc,
            "tags": list(self.tags or []),
            "cost": int(self.cost or 0),
            "provider": self.provider,
        }


# ----------------------------
# Actor location storage
# ----------------------------
def _get_actor_locations(world: Any) -> Dict[str, str]:
    locs = world_get_meta(world, META_ACTOR_LOCS, {})
    if isinstance(locs, dict):
        out: Dict[str, str] = {}
        for k, v in locs.items():
            if k is None:
                continue
            out[str(k)] = str(v) if v is not None else "Unknown"
        return out
    return {}


def _set_actor_location(world: Any, actor: str, location: str) -> None:
    # new store
    locs = _get_actor_locations(world)
    locs[str(actor)] = str(location)
    world_set_meta(world, META_ACTOR_LOCS, locs)

    # legacy store (for older consumers)
    world_set_meta(world, LEGACY_LAST_LOC_KEY.format(actor=actor), str(location))


def get_actor_location(world: Any, actor: str, default: str = "Unknown") -> str:
    # prefer new store
    locs = _get_actor_locations(world)
    if str(actor) in locs:
        return locs[str(actor)]

    # fallback to legacy store
    legacy = world_get_meta(world, LEGACY_LAST_LOC_KEY.format(actor=actor), None)
    if legacy:
        return str(legacy)

    # fallback to agent structure if present (older behavior)
    try:
        agents = get_attr_or_key(world, "agents", None)
        if isinstance(agents, dict):
            a = agents.get(actor)
            if isinstance(a, dict) and a.get("last_location"):
                return str(a["last_location"])
    except Exception:
        pass

    return default


# ----------------------------
# Travel log storage
# ----------------------------
def _append_travel_log(world: Any, entry: Dict[str, Any], max_len: int = 200) -> None:
    log = world_get_meta(world, META_TRAVEL_LOG, [])
    if not isinstance(log, list):
        log = []
    log.append(entry)
    if len(log) > max_len:
        log = log[-max_len:]
    world_set_meta(world, META_TRAVEL_LOG, log)


def get_travel_log(world: Any) -> List[Dict[str, Any]]:
    log = world_get_meta(world, META_TRAVEL_LOG, [])
    return log if isinstance(log, list) else []


# ----------------------------
# Backwards-compatible helper
# ----------------------------
def where(world: Any, actor: str) -> Dict[str, Any]:
    """
    Return last known location for actor.
    Priority:
      1) actor_locations (new)
      2) agent.last_location (if world.agents present)
      3) world meta travel:last_location:<actor> (legacy)
      4) "Unknown"
    """
    loc = get_actor_location(world, actor, default="Unknown")
    return {"ok": True, "actor": actor, "location": loc}


# ----------------------------
# Provider protocol (duck-typed)
# ----------------------------
# A provider is any object with:
#   - provider_id: str  (or id)
#   - list_options(world, from_location) -> List[dict]
#   - apply(world, actor, from_location, to_location, lane=None) -> dict
#
# Option dict minimal shape:
#   { "to_location": str, "lane": str|None, "title": str, "desc": str, "tags": [..], "cost": int }
#
# Apply result dict shape:
#   { ok: bool, ... } optionally includes:
#   - effects: List[dict]
#   - provider: str

def list_options(
    world: Any,
    from_location: str,
    providers: Sequence[Any],
) -> List[Dict[str, Any]]:
    """
    Back-compat alias used by app.main.py and older scripts.
    """
    return list_travel_options(world, from_location, providers)

def list_travel_options(world: Any, from_location: str, providers: Sequence[Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for p in providers or []:
        try:
            pid = getattr(p, "provider_id", None) or getattr(p, "id", None) or "unknown"
            fn = getattr(p, "list_options", None)
            if not callable(fn):
                continue
            opts = fn(world, from_location)
            if not isinstance(opts, list):
                continue
            for o in opts:
                if not isinstance(o, dict):
                    continue
                od = dict(o)
                od.setdefault("provider", pid)
                if "to_location" not in od:
                    continue
                out.append(od)
        except Exception:
            continue
    return out


def _match_option(
    options: Sequence[Dict[str, Any]],
    to_location: str,
    lane: Optional[str],
) -> Optional[Dict[str, Any]]:
    tl = str(to_location)
    ln = (lane or None)

    # Exact match first (to + lane)
    for o in options:
        if str(o.get("to_location")) == tl and (o.get("lane") or None) == ln:
            return o

    # If lane omitted, allow first match by to_location
    if ln is None:
        for o in options:
            if str(o.get("to_location")) == tl:
                return o

    return None


def _find_provider_by_id(providers: Sequence[Any], provider_id: str) -> Optional[Any]:
    for p in providers or []:
        pid = getattr(p, "provider_id", None) or getattr(p, "id", None) or "unknown"
        if pid == provider_id:
            return p
    return None


def apply_travel(
    world: Any,
    actor: str,
    # NEW style (preferred):
    from_location: Optional[str] = None,
    to_location: Optional[str] = None,
    providers: Optional[Sequence[Any]] = None,
    lane: Optional[str] = None,
    # OLD style (legacy aliases):
    src: Optional[str] = None,
    dst: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Apply a travel action using registered providers.

    Accepts BOTH:
      - from_location/to_location (current)
      - src/dst (legacy)

    Returns dict payload that your API can return directly.
    """
    providers = providers or []

    # normalize legacy params
    if from_location is None:
        from_location = src
    if to_location is None:
        to_location = dst

    if not from_location or not to_location:
        return {
            "ok": False,
            "error": "bad_request",
            "message": "Missing from_location/to_location",
            "from_location": from_location,
            "to_location": to_location,
            "lane": lane,
        }

    # gather all options (including provider attribution)
    options = list_travel_options(world, from_location, providers)
    chosen = _match_option(options, to_location, lane)

    # Backwards-compat: support older providers that only implement find_route(...)
    # If no option match, try p.find_route(world, from_location, to_location, lane=...)
    route = None
    route_provider_id: Optional[str] = None
    if not chosen:
        for p in providers or []:
            try:
                fn = getattr(p, "find_route", None)
                if callable(fn):
                    r = fn(world, from_location, to_location, lane=lane)
                    if r:
                        route = r
                        route_provider_id = getattr(p, "provider_id", None) or getattr(p, "id", None) or "provider"
                        break
            except Exception:
                continue

    if not chosen and not route:
        return {
            "ok": False,
            "error": "no_route",
            "message": f"No travel route from {from_location} to {to_location}",
            "from_location": from_location,
            "to_location": to_location,
            "lane": lane,
        }

    provider_id = (chosen or {}).get("provider") or route_provider_id or "unknown"
    provider_obj = _find_provider_by_id(providers, provider_id) if providers else None

    result: Dict[str, Any] = {
        "ok": True,
        "provider": provider_id,
        "actor": actor,
        "from_location": from_location,
        "to_location": to_location,
        "lane": lane,
        "message": f"{actor} travels from {from_location} to {to_location}" + (f" via {lane} lane." if lane else "."),
    }

    # allow provider to enrich/override
    if provider_obj is not None:
        fn = getattr(provider_obj, "apply", None)
        if callable(fn):
            try:
                pr = fn(world, actor, from_location, to_location, lane=lane)
                if isinstance(pr, dict):
                    # merge (provider wins)
                    result.update(pr)
                    result.setdefault("provider", provider_id)
                    result.setdefault("actor", actor)
                    result.setdefault("from_location", from_location)
                    result.setdefault("to_location", to_location)
                    result.setdefault("lane", lane)
            except Exception as e:
                return {
                    "ok": False,
                    "error": "provider_error",
                    "message": f"Provider {provider_id} failed: {type(e).__name__}: {e}",
                    "provider": provider_id,
                }

    # persist actor location in BOTH new + legacy stores
    _set_actor_location(world, actor, to_location)

    # persist last seen ts (legacy key) + agent structure if present (legacy behavior)
    ts = now_ts()
    world_set_meta(world, LEGACY_LAST_SEEN_KEY.format(actor=actor), ts)
    try:
        agents = get_attr_or_key(world, "agents", None)
        if isinstance(agents, dict):
            a = agents.get(actor)
            if isinstance(a, dict):
                a["last_location"] = str(to_location)
                a["last_seen_ts"] = ts
    except Exception:
        pass

    # tick + travel log
    tick = bump_tick(world, 1)
    entry = {
        "ts": ts,
        "tick": tick,
        "actor": actor,
        "from": from_location,
        "to": to_location,
        "lane": lane,
        "provider": provider_id,
        "tags": list((chosen or {}).get("tags") or []),
        # include route blob if it came from legacy find_route()
        "route": route if route is not None else None,
    }
    _append_travel_log(world, entry)

    result["tick"] = tick
    return result
