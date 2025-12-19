from __future__ import annotations

from typing import Any, Dict

def register(registry, app, world) -> None:
    """
    Example addon that:
      - adds one debug endpoint
      - hooks realm selection to stamp a tag automatically for this realm
    """

    def add_routes(app):
        @app.get("/addon/realm-lorkhan/ping")
        def ping() -> Dict[str, Any]:
            return {"ok": True, "addon": "realm_lorkhan"}

    def on_realm_selection(world, req, applied):
        # If selection happens in the RealmOfLorkhan, ensure a tag exists.
        if getattr(req, "location", "") == "RealmOfLorkhan":
            # applied is usually a list of effects applied; we can append a meta-note
            applied.append({"channel": "tag", "tag": "in_realm_of_lorkhan", "delta": 0.0, "note": "addon"})
        return None

    registry.add_routes(add_routes)
    registry.add_realm_selection(on_realm_selection)
