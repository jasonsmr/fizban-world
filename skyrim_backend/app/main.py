from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from .state import WORLD
from . import logic
from .realm import RealmSelectionIn, RealmSelectionOut, RealmEffect


app = FastAPI(title="Fizban Skyrim Backend", version="0.1.0")


class HealthOut(BaseModel):
    ok: bool = True
    tick: int
    agents: List[str]


class FavorApplyIn(BaseModel):
    actor: str
    channel: str = Field(..., description="divine|daedra|faction|global")
    key: str
    delta: float
    reason: str = "unknown"


class FavorApplyOut(BaseModel):
    ok: bool = True
    actor: str
    channel: str
    key: str
    new: Dict[str, Any]


class GossipItem(BaseModel):
    rumor_id: str
    about: str
    claim: str
    truthiness: float = 0.5
    heat: float = 0.5
    origin: str
    location: str
    tags: List[str] = []


class GossipPropIn(BaseModel):
    source: str
    receivers: List[str]
    strength: float = 0.5
    item: GossipItem


class GossipPropOut(BaseModel):
    ok: bool = True
    rumor_id: str
    receivers: List[str]
    tick: int


class SkyrimEventIn(BaseModel):
    event_id: str
    t: str
    ts_unix: Optional[float] = None
    actor: str
    target: Optional[str] = None
    location: str = "Unknown"
    tags: List[str] = []
    intensity: float = 0.5
    payload: Dict[str, Any] = {}


@app.get("/health", response_model=HealthOut)
def health():
    return HealthOut(ok=True, tick=WORLD.tick, agents=sorted(list(WORLD.agents.keys())))


@app.get("/npc/{name}")
def npc_get(name: str):
    a = logic.ensure_agent(WORLD, name)
    return a.model_dump()


@app.post("/decide")
def decide(ev: SkyrimEventIn):
    # ensure involved agents exist
    logic.ensure_agent(WORLD, ev.actor)
    if ev.target:
        logic.ensure_agent(WORLD, ev.target)

    out = logic.decide(WORLD, ev.model_dump())
    return out


@app.post("/favor/apply", response_model=FavorApplyOut)
def favor_apply(req: FavorApplyIn):
    logic.ensure_agent(WORLD, req.actor)
    logic.apply_favor(WORLD, req.actor, req.channel, req.key, req.delta, req.reason)
    return FavorApplyOut(ok=True, actor=req.actor, channel=req.channel, key=req.key, new=logic.get_agent(WORLD, req.actor).model_dump())


@app.post("/gossip/propagate", response_model=GossipPropOut)
def gossip_prop(req: GossipPropIn):
    logic.ensure_agent(WORLD, req.source)
    for r in req.receivers:
        logic.ensure_agent(WORLD, r)
    logic.propagate_gossip(WORLD, req.source, req.receivers, req.strength, req.item.model_dump())
    return GossipPropOut(ok=True, rumor_id=req.item.rumor_id, receivers=req.receivers, tick=WORLD.tick)


@app.post("/realm/selection", response_model=RealmSelectionOut)
def realm_selection(req: RealmSelectionIn):
    """
    Adapter: in-game start-room choices -> world state changes.
    Your Skyrim mod can call this once per “shrine / guild / pact / race affinity” selection.
    """
    logic.ensure_agent(WORLD, req.actor)

    applied: List[RealmEffect] = []
    # Apply effects
    for eff in req.effects:
        ch = eff.channel.lower().strip()
        if ch in ("divine", "daedra", "faction"):
            if not eff.key:
                continue
            logic.apply_favor(WORLD, req.actor, ch, eff.key, eff.delta, eff.note or req.selection_id)
            applied.append(eff)
        elif ch == "tag":
            if eff.tag:
                a = logic.get_agent(WORLD, req.actor)
                if eff.tag not in a.tags:
                    a.tags.append(eff.tag)
                applied.append(eff)
        elif ch == "trust":
            a = logic.get_agent(WORLD, req.actor)
            a.trust = max(0.0, min(1.0, a.trust + eff.delta))
            applied.append(eff)
        elif ch == "fear":
            a = logic.get_agent(WORLD, req.actor)
            a.fear = max(0.0, min(1.0, a.fear + eff.delta))
            applied.append(eff)
        elif ch == "favor":
            a = logic.get_agent(WORLD, req.actor)
            a.favor = max(0.0, min(1.0, a.favor + eff.delta))
            applied.append(eff)

    # Apply request-level tags
    if req.tags:
        a = logic.get_agent(WORLD, req.actor)
        for t in req.tags:
            t = t.strip()
            if t and t not in a.tags:
                a.tags.append(t)

    a = logic.get_agent(WORLD, req.actor)
    a.last_location = req.location

    return RealmSelectionOut(
        ok=True,
        actor=req.actor,
        selection_id=req.selection_id,
        applied=applied,
        tick=WORLD.tick,
    )
