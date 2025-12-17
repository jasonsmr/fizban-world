from __future__ import annotations

import time
from typing import Dict, List

from .models import NPCState, GossipItem


class WorldState:
    def __init__(self) -> None:
        self.tick: int = 0
        self.npcs: Dict[str, NPCState] = {}
        self.gossip: Dict[str, GossipItem] = {}

    def get_or_create_npc(self, name: str) -> NPCState:
        if name not in self.npcs:
            self.npcs[name] = NPCState(name=name, last_seen_ts=time.time())
        return self.npcs[name]

    def touch(self, npc_name: str, location: str | None = None) -> None:
        npc = self.get_or_create_npc(npc_name)
        npc.last_seen_ts = time.time()
        if location:
            npc.last_location = location

    def add_gossip(self, item: GossipItem) -> None:
        self.gossip[item.rumor_id] = item

    def list_gossip(self) -> List[GossipItem]:
        return list(self.gossip.values())


WORLD = WorldState()
