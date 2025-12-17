from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EventType(str, Enum):
    DIALOGUE = "DIALOGUE"
    COMBAT = "COMBAT"
    QUEST = "QUEST"
    FAVOR = "FAVOR"
    LOCATION = "LOCATION"
    EMOTE = "EMOTE"


class SkyrimEvent(BaseModel):
    event_id: str = Field(..., description="Unique id from game side")
    t: EventType = Field(..., description="Event type")
    ts_unix: Optional[float] = Field(None, description="Unix timestamp (seconds)")
    actor: str = Field(..., description="Who initiated the event (Player/NPC)")
    target: Optional[str] = Field(None, description="Optional target NPC/faction")
    location: Optional[str] = Field(None, description="Cell/area name")
    tags: List[str] = Field(default_factory=list, description="Freeform tags")
    intensity: float = Field(0.5, ge=0.0, le=1.0, description="0..1")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Extra event data")


class DecisionOut(BaseModel):
    actor: str
    decision: str
    confidence: float
    reason_tags: List[str] = Field(default_factory=list)
    say: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NPCState(BaseModel):
    name: str
    trust: float = 0.5
    fear: float = 0.1
    favor: float = 0.5
    gossip_heat: float = 0.0
    last_location: str = "Unknown"
    last_seen_ts: float = 0.0
    tags: List[str] = Field(default_factory=list)

    # Optional: faction standings (Stormcloaks, ThievesGuild, etc.)
    faction: Dict[str, float] = Field(default_factory=dict)

    # Optional: religious/daedric favor channels
    divine: Dict[str, float] = Field(default_factory=dict)
    daedra: Dict[str, float] = Field(default_factory=dict)


class GossipItem(BaseModel):
    rumor_id: str
    about: str
    claim: str
    truthiness: float = Field(0.5, ge=0.0, le=1.0)
    heat: float = Field(0.2, ge=0.0, le=1.0)
    origin: str
    location: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class GossipPropagateIn(BaseModel):
    source: str
    receivers: List[str]
    item: GossipItem
    strength: float = Field(0.5, ge=0.0, le=1.0)


class FavorApplyIn(BaseModel):
    actor: str
    channel: str = Field(..., description="faction|divine|daedra")
    key: str = Field(..., description="e.g. 'Stormcloaks', 'Akatosh', 'MolagBal'")
    delta: float = Field(..., ge=-1.0, le=1.0)
    reason: str = "unknown"
