import json, os
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional

# Minimal NPC state for early integration

@dataclass
class NPCState:
    npc_id: str
    faction_id: str
    trust: int = 50
    fear: int = 0
    respect: int = 50
    curiosity: int = 50
    intent: str = "neutral"  # benevolent|neutral|selfish|deceptive
    memory_tags: List[str] = field(default_factory=list)

    def clamp(self):
        self.trust = max(0, min(100, int(self.trust)))
        self.fear = max(0, min(100, int(self.fear)))
        self.respect = max(0, min(100, int(self.respect)))
        self.curiosity = max(0, min(100, int(self.curiosity)))

class NPCStateDB:
    def __init__(self, npcs: Optional[Dict[str,NPCState]]=None):
        self.npcs: Dict[str,NPCState] = npcs or {}

    @staticmethod
    def load(path: str) -> 'NPCStateDB':
        if not path or not os.path.exists(path):
            return NPCStateDB()
        with open(path,'r',encoding='utf-8') as f:
            data=json.load(f)
        npcs={}
        for obj in data.get('npcs',[]):
            npc=NPCState(**obj)
            npc.clamp()
            npcs[npc.npc_id]=npc
        return NPCStateDB(npcs)

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        payload={"schema":"fizban.npc_state.v0.1","npcs":[asdict(n) for n in self.npcs.values()]}
        tmp=path+'.tmp'
        with open(tmp,'w',encoding='utf-8') as f:
            json.dump(payload,f,indent=2,ensure_ascii=False)
        os.replace(tmp,path)

    def ensure_default(self):
        # One default NPC to start: "local watcher"
        if "npc.local.watcher" not in self.npcs:
            self.npcs["npc.local.watcher"] = NPCState(
                npc_id="npc.local.watcher",
                faction_id="xi.faction.local",
                trust=35,
                fear=10,
                respect=45,
                curiosity=55,
                intent="neutral",
                memory_tags=[]
            )

    def tick(self, ws):
        """Update intents based on ws tension/rumor/flags. Cheap but effective."""
        self.ensure_default()
        tension = int(getattr(ws,'tension_index',0))
        flags = getattr(ws,'flags',None)
        status = set(flags.status) if flags else set()
        facts = set(flags.facts) if flags else set()

        for npc in self.npcs.values():
            rp = int(getattr(ws,'rumor_pressure',{}).get(npc.faction_id, 0))

            # rumor affects trust baseline
            npc.trust = max(0, min(100, npc.trust + rp))

            # tension increases fear a bit
            npc.fear = max(0, min(100, npc.fear + (1 if tension >= 50 else 0)))

            # status tags alter perception
            if "WITNESS_LEFT" in status:
                npc.curiosity = min(100, npc.curiosity + 1)
            if "STRAINED" in status:
                npc.respect = max(0, npc.respect - 1)

            # memory tags: only store milestone facts
            for f in facts:
                if f.startswith('FACT_') and f not in npc.memory_tags:
                    npc.memory_tags.append(f)

            # intent switch rules
            if npc.fear >= 70 and npc.trust <= 30:
                npc.intent = "deceptive"
            elif npc.trust >= 70 and npc.respect >= 60:
                npc.intent = "benevolent"
            elif npc.respect <= 35 and npc.curiosity >= 60:
                npc.intent = "selfish" if rp < 0 else "neutral"
            else:
                npc.intent = "neutral"

            npc.clamp()

    def summary(self) -> str:
        if not self.npcs:
            return ""
        lines=[]
        for n in sorted(self.npcs.values(), key=lambda x: x.npc_id):
            lines.append(f"{n.npc_id} [{n.intent}] trust={n.trust} fear={n.fear} respect={n.respect} curiosity={n.curiosity} faction={n.faction_id}")
        return "\n".join(lines)
