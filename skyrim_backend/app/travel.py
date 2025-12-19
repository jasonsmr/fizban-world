# app/travel.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .compat import bump_tick, now_ts, world_get_meta, world_set_meta


# ----------------------------
# Meta keys (world.meta)
# ----------------------------
META_ACTOR_LOCS = "actor_locations"   # Dict[str, str]
META_TRAVEL_LOG = "travel_log"        # List[dict]


@dataclass
class TravelOption:
    to_location: str
    lane: Optional[str] = None
    title: str = ""
    desc: str = ""
    tags: List[str] = None
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


def _get_actor_locations(world: Any) -> Dict[str, str]:
    locs = world_get_meta(world, META_ACTOR_LOCS, {})
    if isinstance(locs, dict):
        # normalize values to strings
        out: Dict[str, str] = {}
        for k, v in locs.items():
            if k is None:
                continue
            out[str(k)] = str(v) if v is not None else "Unknown"
        return out
    return {}


def _set_actor_location(world: Any, actor: str, location: str) -> None:
    locs = _get_actor_locations(world)
    locs[str(actor)] = str(location)
    world_set_meta(world, META_ACTOR_LOCS, locs)


def get_actor_location(world: Any, actor: str, default: str = "Unknown") -> str:
    locs = _get_actor_locations(world)
    return locs.get(str(actor), default)


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
# Provider protocol (duck-typed)
# ----------------------------
# A provider is any object with:
#   - provider_id: str
#   - list_options(world, from_location) -> List[dict]
#   - apply(world, actor, from_location, to_location, lane=None) -> dict
#
# Option dict minimal shape:
#   { "to_location": str, "lane": str|None, "title": str, "desc": str, "tags": [..], "cost": int }
#
# Apply result dict shape:
#   { ok: bool, ... } optionally includes:
#   - effects: List[dict]  (channel/key/delta/tag/note)  (we’ll apply these to actor in logic later if desired)
#   - provider: str


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
                # normalize required fields
                if "to_location" not in od:
                    continue
                out.append(od)
        except Exception:
            # keep providers isolated; one bad provider shouldn't kill the endpoint
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


def apply_travel(
    world: Any,
    actor: str,
    from_location: str,
    to_location: str,
    providers: Sequence[Any],
    lane: Optional[str] = None,
) -> Dict[str, Any]:
    # gather all options (including provider attribution)
    options = list_travel_options(world, from_location, providers)
    chosen = _match_option(options, to_location, lane)

    if not chosen:
        return {
            "ok": False,
            "error": "no_route",
            "message": f"No travel route from {from_location} to {to_location}",
            "from_location": from_location,
            "to_location": to_location,
            "lane": lane,
        }

    provider_id = chosen.get("provider") or "unknown"

    # find the provider object by id, and if it has apply() call it
    provider_obj = None
    for p in providers or []:
        pid = getattr(p, "provider_id", None) or getattr(p, "id", None) or "unknown"
        if pid == provider_id:
            provider_obj = p
            break

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

    # persist actor location + travel log
    _set_actor_location(world, actor, to_location)
    tick = bump_tick(world, 1)
    entry = {
        "ts": now_ts(),
        "tick": tick,
        "actor": actor,
        "from": from_location,
        "to": to_location,
        "lane": lane,
        "provider": provider_id,
        "tags": list(chosen.get("tags") or []),
    }
    _append_travel_log(world, entry)

    result["tick"] = tick
    return result
