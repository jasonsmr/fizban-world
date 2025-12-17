from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class RealmEffect(BaseModel):
    """
    A single effect coming from an in-game selection.
    Example:
      {"channel":"divine","key":"Akatosh","delta":0.05,"tag":"start_prayed"}
      {"channel":"faction","key":"ThievesGuild","delta":0.10}
    """
    channel: str = Field(..., description="divine|daedra|faction|tag|trust|fear|favor")
    key: Optional[str] = Field(None, description="name within the channel (e.g. Akatosh, Companions)")
    delta: float = Field(0.0, description="signed change")
    tag: Optional[str] = Field(None, description="optional tag to add")
    note: Optional[str] = None


class RealmSelectionIn(BaseModel):
    actor: str = "Player"
    selection_id: str = Field(..., description="e.g. realm_shrine_akatosh, realm_guild_thieves")
    location: str = "RealmOfLorkhan"
    effects: List[RealmEffect] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class RealmSelectionOut(BaseModel):
    ok: bool = True
    actor: str
    selection_id: str
    applied: List[RealmEffect]
    tick: int
