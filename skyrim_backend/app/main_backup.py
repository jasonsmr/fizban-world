from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import logic
from . import addons
from .compat import format_exception_payload, get_attr_or_key, safe_model_dump
from .state import WORLD
from .version import __version__

DEBUG = os.getenv("FIZBAN_DEBUG", "1") == "1"

app = FastAPI(title="Fizban Skyrim Backend", version=__version__)

ADDON_REGISTRY = None  # populated on startup


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
    hook_errors: List[str] = Field(default_factory=list)


@app.on_event("startup")
def _startup_load_addons():
    global ADDON_REGISTRY
    ADDON_REGISTRY = addons.load_addons(app=app, world=WORLD, compat=__import__("app.compat", fromlist=["*"]))


@app.get("/addons")
def addons_list():
    reg = ADDON_REGISTRY
    if not reg:
        return {"ok": True, "enabled": (os.environ.get("FIZBAN_ADDONS") or "").strip(), "addons": {}, "errors": {}}
    return {
        "ok": True,
        "backend_version": __version__,
        "enabled": (os.environ.get("FIZBAN_ADDONS") or "").strip(),
        "addons": {k: vars(v) for k, v in reg.addons.items()},
        "errors": reg.load_errors,
        "loaded_at": reg.loaded_at,
    }


@app.get("/debug/addons")
def addons_debug():
    if not DEBUG:
        return {"ok": False, "error": "debug disabled"}
    return addons_list()


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
    effects = [safe_model_dump(e) for e in req.effects]
    applied, tick = logic.apply_realm_selection(
        WORLD,
        actor=req.actor,
        selection_id=req.selection_id,
        location=req.location,
        effects=effects,
        tags=req.tags,
    )

    hook_errors: List[str] = []
    reg = ADDON_REGISTRY
    if reg:
        addons.run_hook_list(reg.hooks.on_realm_selection, WORLD, req, applied, errors=hook_errors)

    return RealmSelectionOut(
        ok=True,
        actor=req.actor,
        selection_id=req.selection_id,
        applied=[
            AppliedEffectOut(
                channel=a.get("channel"),
                key=a.get("key"),
                delta=float(a.get("delta") or 0.0),
                tag=a.get("tag"),
                note=a.get("note"),
            )
            for a in applied
            if isinstance(a, dict)
        ],
        tick=tick,
        hook_errors=hook_errors,
    )

# ---- Travel API (core) ----
from . import travel as travel_logic

class TravelOptionsOut(BaseModel):
    ok: bool = True
    from_location: str
    options: List[Dict[str, Any]] = Field(default_factory=list)

class TravelGoIn(BaseModel):
    actor: str
    from_location: str
    to_location: str
    lane: Optional[str] = None

@app.get("/travel/options", response_model=TravelOptionsOut)
def travel_options(from_location: str) -> TravelOptionsOut:
    reg = getattr(ADDON_REGISTRY, "registry", None) if hasattr(ADDON_REGISTRY, "registry") else None
    providers = []
    try:
        providers = list(getattr(reg, "travel_providers", [])) if reg else []
    except Exception:
        providers = []
    opts = travel_logic.list_travel_options(WORLD, from_location, providers)
    return TravelOptionsOut(ok=True, from_location=from_location, options=opts)

@app.post("/travel/go")
def travel_go(req: TravelGoIn) -> Dict[str, Any]:
    reg = getattr(ADDON_REGISTRY, "registry", None) if hasattr(ADDON_REGISTRY, "registry") else None
    providers = []
    try:
        providers = list(getattr(reg, "travel_providers", [])) if reg else []
    except Exception:
        providers = []
    return travel_logic.apply_travel(
        WORLD,
        actor=req.actor,
        src=req.from_location,
        dst=req.to_location,
        providers=providers,
        lane=req.lane,
    )

from . import travel

class TravelOptionsOut(BaseModel):
    ok: bool = True
    from_location: str
    options: List[Dict[str, Any]] = Field(default_factory=list)

class TravelGoIn(BaseModel):
    actor: str
    from_location: str
    to_location: str
    lane: Optional[str] = None

@app.get("/travel/options", response_model=TravelOptionsOut)
def travel_options(from_location: str) -> TravelOptionsOut:
    opts = travel.list_options(WORLD, from_location=from_location)
    return TravelOptionsOut(ok=True, from_location=from_location, options=opts)

@app.post("/travel/go")
def travel_go(req: TravelGoIn) -> Dict[str, Any]:
    return travel.apply_travel(
        WORLD,
        actor=req.actor,
        from_location=req.from_location,
        to_location=req.to_location,
        lane=req.lane,
    )
