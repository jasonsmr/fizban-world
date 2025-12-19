from __future__ import annotations

from typing import Any, Dict


def register(app, world, compat, state):
    # Route example
    @app.get("/ping")
    def ping() -> Dict[str, Any]:
        return {"ok": True, "addon": "example_ping"}

    # Hook example: observe realm selection
    def on_realm_selection(world, req, applied):
        # return nothing, just observe (or return effect dicts to append)
        return None

    state.registry.on_realm_selection.append(on_realm_selection)
