from __future__ import annotations

import traceback
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def _unhandled_exception(request: Request, exc: Exception):
        # Always return JSON so curl | jq never explodes on "Internal Server Error"
        payload: Dict[str, Any] = {
            "ok": False,
            "error": type(exc).__name__,
            "message": str(exc),
            "path": request.url.path,
        }

        # Include traceback only when explicitly enabled (dev mode)
        # You can toggle this with: export FIZBAN_DEBUG_TRACE=1
        import os
        if os.environ.get("FIZBAN_DEBUG_TRACE", "").strip() == "1":
            payload["trace"] = traceback.format_exc().splitlines()

        return JSONResponse(status_code=500, content=payload)
