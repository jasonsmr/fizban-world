"""
app.logic
Glue-layer functions used by app.main routes.

This file exists primarily to keep "business logic" out of the FastAPI route module
and to make future Skyrim adapters (Realm of Lorkhan, SKSE, Skyrim Platform, etc.)
plug in cleanly.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def _get_state_module():
    # Import inside functions to avoid circular imports during uvicorn reload.
    from . import state
    return state


def _get_puck_module():
    from . import puck
    return puck


def _get_realm_module():
    from . import realm
    return realm


def decide(event: Any) -> Any:
    """
    Given an event (usually a Pydantic model), update world state and return a decision.
    """
    state = _get_state_module()
    puck = _get_puck_module()

    world = getattr(state, "WORLD", None)
    if world is None and hasattr(state, "get_world"):
        world = state.get_world()

    # Support either puck.decide(event, world) or puck.puck_decide(event, world)
    if hasattr(puck, "decide"):
        return puck.decide(event, world)
    if hasattr(puck, "puck_decide"):
        return puck.puck_decide(event, world)

    raise RuntimeError("puck module has no decide() or puck_decide()")


def apply_favor(req: Any) -> Dict[str, Any]:
    """
    Apply a favor delta into the world state.
    Expects req fields: actor, channel ('divine'|'daedra'|'faction'), key, delta, reason(optional)
    """
    state = _get_state_module()
    world = getattr(state, "WORLD", None)
    if world is None and hasattr(state, "get_world"):
        world = state.get_world()

    actor = getattr(req, "actor", None)
    channel = getattr(req, "channel", None)
    key = getattr(req, "key", None)
    delta = float(getattr(req, "delta", 0.0))

    if actor is None or channel is None or key is None:
        raise ValueError("apply_favor requires actor, channel, key")

    # Find/create NPC record
    if hasattr(world, "ensure_npc"):
        npc = world.ensure_npc(actor)
    elif hasattr(world, "npcs"):
        npc = world.npcs.get(actor)
        if npc is None and hasattr(world, "make_npc"):
            npc = world.make_npc(actor)
            world.npcs[actor] = npc
    else:
        raise RuntimeError("World state has no ensure_npc()/npcs mapping")

    # Apply channel-specific delta
    if channel == "divine":
        m = getattr(npc, "divine", None)
        if m is None:
            m = {}
            setattr(npc, "divine", m)
        m[key] = float(m.get(key, 0.0)) + delta
    elif channel == "daedra":
        m = getattr(npc, "daedra", None)
        if m is None:
            m = {}
            setattr(npc, "daedra", m)
        m[key] = float(m.get(key, 0.0)) + delta
    else:
        # treat as faction-like bucket
        m = getattr(npc, "faction", None)
        if m is None:
            m = {}
            setattr(npc, "faction", m)
        m[key] = float(m.get(key, 0.0)) + delta

    # Return a small response payload
    return {
        "ok": True,
        "actor": actor,
        "channel": channel,
        "key": key,
        "delta": delta,
        "new": npc.model_dump() if hasattr(npc, "model_dump") else npc.__dict__,
    }


def propagate_gossip(req: Any) -> Dict[str, Any]:
    """
    Propagate a rumor item from a source to receivers.
    Expects req fields: source, receivers(list), strength(float), item(rumor object)
    """
    state = _get_state_module()
    world = getattr(state, "WORLD", None)
    if world is None and hasattr(state, "get_world"):
        world = state.get_world()

    source = getattr(req, "source", None)
    receivers = list(getattr(req, "receivers", []) or [])
    item = getattr(req, "item", None)

    if source is None or item is None:
        raise ValueError("propagate_gossip requires source and item")

    rumor_id = getattr(item, "rumor_id", None) or getattr(item, "id", None) or "rumor-unknown"

    # If your world has a dedicated gossip store, use it; otherwise do a simple per-NPC heat bump.
    strength = float(getattr(req, "strength", 0.0))
    heat = float(getattr(item, "heat", 0.0))

    if hasattr(world, "ensure_npc"):
        for r in receivers:
            npc = world.ensure_npc(r)
            # bump gossip_heat (simple global heat signal per NPC)
            if hasattr(npc, "gossip_heat"):
                npc.gossip_heat = float(getattr(npc, "gossip_heat", 0.0)) + (strength * heat * 0.1)

    return {"ok": True, "rumor_id": rumor_id, "receivers": receivers, "tick": getattr(world, "tick", 0)}


def realm_ingest(req: Any) -> Dict[str, Any]:
    """
    Realm of Lorkhan adapter hook.
    For now, this is a stub that can translate Realm events into SkyrimEvents later.
    """
    realm = _get_realm_module()
    # If you later add realm.translate_to_events(req) or similar, this file is where it goes.
    if hasattr(realm, "ingest"):
        return realm.ingest(req)

    return {"ok": True, "note": "realm_ingest stub (no realm.ingest() yet)"}

# ---------------------------------------------------------------------------
# Compat helper: main.py expects logic.ensure_agent(world, name)
# ---------------------------------------------------------------------------
def ensure_agent(world, name: str):
    """
    Ensure an agent/NPC exists in world state. Returns the agent object.
    Supports worlds implemented as:
      - world.ensure_agent(name) method, OR
      - world.npcs dict-like container
    """
    # Preferred: world provides its own method
    try:
        fn = getattr(world, "ensure_agent", None)
        if callable(fn):
            return fn(name)
    except Exception:
        pass

    # Fallback: create in world.npcs
    npcs = getattr(world, "npcs", None)
    if npcs is None:
        raise AttributeError("World has no ensure_agent() and no .npcs container")

    if name in npcs:
        return npcs[name]

    # Try to use a typed model if your models.py provides it
    try:
        from .models import NPCState  # optional
        npc = NPCState(name=name)
    except Exception:
        npc = {
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

    npcs[name] = npc
    return npc
