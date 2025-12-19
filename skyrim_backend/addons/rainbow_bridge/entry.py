from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Rainbow Bridge travel lanes (you can expand later)
LANES = {
    "gold": {"title": "Golden Arch", "tag": "boon"},
    "red": {"title": "Crimson Run", "tag": "speed"},
    "blue": {"title": "Azure Slip", "tag": "ice"},
    "green": {"title": "Emerald Veil", "tag": "fey"},
}

# Minimal starter routes (expand as you build regions)
ROUTES = {
    "RainbowBridge": ["Whiterun", "Riverwood", "Solitude", "Windhelm", "Riften"],
}


@dataclass
class RainbowBridgeProvider:
    id: str = "rainbow_bridge"

    def list_options(self, world: Any, from_location: str) -> List[Dict[str, Any]]:
        dests = ROUTES.get(from_location, [])
        if not dests:
            return []

        out: List[Dict[str, Any]] = []
        for dst in dests:
            for lane, info in LANES.items():
                out.append(
                    {
                        "to_location": dst,
                        "lane": lane,
                        "title": f"{info['title']} → {dst}",
                        "desc": f"Traverse the Rainbow Bridge ({lane}) to {dst}.",
                        "tags": ["rainbow_bridge", info.get("tag", "")],
                        "cost": 0,
                    }
                )
        return out

    def apply_travel(self, world: Any, actor: str, from_location: str, to_location: str, lane: Optional[str] = None) -> Dict[str, Any]:
        if from_location not in ROUTES:
            return {"ok": False, "error": "not_provider"}
        if to_location not in ROUTES[from_location]:
            return {"ok": False, "error": "no_route"}

        if lane is not None and lane not in LANES:
            return {"ok": False, "error": "bad_lane", "message": f"Unknown lane: {lane}"}

        # Minimal "state" impact for now (grow later: favors, tags, costs, etc.)
        # store last location per-actor if you want; for now store global
        meta = getattr(world, "meta", None)
        # don't assume shape; compat helpers will exist, but keep this addon standalone-safe
        try:
            if isinstance(meta, dict):
                meta["last_location"] = to_location
                meta["last_lane"] = lane
                meta["last_actor"] = actor
        except Exception:
            pass

        return {
            "ok": True,
            "provider": self.id,
            "actor": actor,
            "from_location": from_location,
            "to_location": to_location,
            "lane": lane,
            "message": f"{actor} travels from {from_location} to {to_location} via {lane or 'default'} lane.",
        }


def register(app, world, compat, state):
    provider = RainbowBridgeProvider()

    # Register with addon registry (preferred path)
    try:
        state.registry.travel_providers.append(provider)
    except Exception:
        # if registry missing, ignore; we'll also register in world meta
        pass

    # Register into world meta so core travel can still find it even if main.py changes
    try:
        cur = compat.world_get_meta(world, "travel_providers", default=[])
        if not isinstance(cur, list):
            cur = []
        # avoid duplicates
        if provider not in cur:
            cur.append(provider)
        compat.world_set_meta(world, "travel_providers", cur)
    except Exception:
        pass
