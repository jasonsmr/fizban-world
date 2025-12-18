from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import logic
from .compat import format_exception_payload, get_attr_or_key
from .state import WORLD  # keep your singleton world


DEBUG = os.getenv("FIZBAN_DEBUG", "1") == "1"

app = FastAPI(title="Fizban Skyrim Backend", version="0.2.0")


@app.middleware("http")
async def trace_mw(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id") or uuid.uuid4().hex[:12]
    request.state.trace_id = trace_id
    resp = await call_next(request)
    resp.headers["x-trace-id"] = trace_id
    return resp


@app.exception_handler(Exception)
async def any_exception_handler(request: Request, exc: Exception):
    trace_id = getattr(request.state, "trace_id", "no-trace")
    payload = format_exception_payload(exc, trace_id=trace_id, debug=DEBUG)
    return JSONResponse(status_code=500, content=payload)


class HealthOut(BaseModel):
    ok: bool = True
    tick: int = 0
    agents: List[str] = Field(default_factory=list)


class EffectIn(BaseModel):
    channel: str
    key: Optional[str] = None
    delta: float = 0.0
    tag: Optional[str] = None
    note: Optional[str] = None


class RealmSelectionIn(BaseModel):
    actor: str
    selection_id: str
    location: str
    effects: List[EffectIn] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class AppliedEffectOut(BaseModel):
    channel: str
    key: Optional[str] = None
    delta: float = 0.0
    tag: Optional[str] = None
    note: Optional[str] = None


class RealmSelectionOut(BaseModel):
    ok: bool = True
    actor: str
    selection_id: str
    applied: List[AppliedEffectOut] = Field(default_factory=list)
    tick: int = 0


@app.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    tick = get_attr_or_key(WORLD, "tick", 0)
    try:
        tick_i = int(tick)
    except Exception:
        tick_i = 0
    return HealthOut(ok=True, tick=tick_i, agents=logic.list_agents(WORLD))


@app.get("/npc/{name}")
def npc_get(name: str) -> Dict[str, Any]:
    a = logic.get_agent(WORLD, name)
    return dict(a)


@app.post("/realm/selection", response_model=RealmSelectionOut)
def realm_selection(req: RealmSelectionIn) -> RealmSelectionOut:
    applied, tick = logic.apply_realm_selection(
        WORLD,
        actor=req.actor,
        selection_id=req.selection_id,
        location=req.location,
        effects=[e.model_dump() if hasattr(e, "model_dump") else e.dict() for e in req.effects],
        tags=req.tags,
    )
    return RealmSelectionOut(
        ok=True,
        actor=req.actor,
        selection_id=req.selection_id,
        applied=[
            AppliedEffectOut(
                channel=a.channel,
                key=a.key,
                delta=a.delta,
                tag=a.tag,
                note=a.note,
            )
            for a in applied
        ],
        tick=tick,
    )
