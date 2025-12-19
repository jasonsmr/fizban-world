from __future__ import annotations

import importlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .version import __version__
from .compat import version_satisfies

# filesystem addons live here (repo_root/addons/*)
ADDONS_DIR = Path(__file__).resolve().parent.parent / "addons"


@dataclass
class AddonInfo:
    name: str
    version: str
    path: str
    enabled: bool
    manifest: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class HookRegistry:
    on_realm_selection: List[Callable[[Any, Any, List[Any]], Optional[List[Dict[str, Any]]]]] = field(default_factory=list)


@dataclass
class AddonRegistry:
    addons: Dict[str, AddonInfo] = field(default_factory=dict)
    hooks: HookRegistry = field(default_factory=HookRegistry)
    load_errors: Dict[str, str] = field(default_factory=dict)
    loaded_at: float = field(default_factory=time.time)


def _parse_enabled() -> Tuple[bool, List[str]]:
    raw = (os.environ.get("FIZBAN_ADDONS") or "").strip()
    if not raw:
        return False, []
    if raw.lower() == "all":
        return True, []
    items = [x.strip() for x in raw.split(",") if x.strip()]
    return False, items


def _is_enabled(addon_id: str, enable_all: bool, allow: List[str]) -> bool:
    if enable_all:
        return True
    return addon_id in allow


def _load_manifest(manifest_path: Path) -> Dict[str, Any]:
    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _import_entrypoint(ep: str):
    # "pkg.mod:func"
    if ":" not in ep:
        raise ValueError(f"Bad entrypoint: {ep!r} (expected 'module:callable')")
    mod, fn = ep.split(":", 1)
    m = importlib.import_module(mod)
    cb = getattr(m, fn, None)
    if not callable(cb):
        raise TypeError(f"Entrypoint not callable: {ep!r}")
    return cb


def load_addons(app, world, compat) -> AddonRegistry:
    reg = AddonRegistry()
    enable_all, allow = _parse_enabled()

    if not ADDONS_DIR.exists():
        return reg

    for addon_dir in sorted([p for p in ADDONS_DIR.iterdir() if p.is_dir()]):
        manifest_path = addon_dir / "manifest.json"
        addon_id = addon_dir.name

        if not manifest_path.exists():
            # Not fatal; skip
            continue

        enabled = _is_enabled(addon_id, enable_all, allow)
        info = AddonInfo(
            name=addon_id,
            version="0.0.0",
            path=str(addon_dir),
            enabled=enabled,
            manifest={},
        )

        try:
            manifest = _load_manifest(manifest_path)
            info.manifest = manifest
            info.version = str(manifest.get("version") or "0.0.0")

            requires = str(manifest.get("requires_backend") or "")
            if requires and not version_satisfies(__version__, requires):
                info.enabled = False
                info.error = f"requires_backend {requires} not satisfied by backend {__version__}"
                reg.addons[addon_id] = info
                reg.load_errors[addon_id] = info.error
                continue

            if not enabled:
                reg.addons[addon_id] = info
                continue

            entrypoint = manifest.get("entrypoint")
            if not entrypoint:
                raise ValueError("manifest missing 'entrypoint'")

            cb = _import_entrypoint(str(entrypoint))

            # Minimal "state" object passed to addons
            class _State:
                def __init__(self, registry: HookRegistry):
                    self.registry = registry

            state = _State(reg.hooks)

            # Standard addon signature:
            # register(app, world, compat, state)
            cb(app, world, compat, state)

            reg.addons[addon_id] = info

        except Exception as e:
            info.enabled = False
            info.error = f"{type(e).__name__}: {e}"
            reg.addons[addon_id] = info
            reg.load_errors[addon_id] = info.error

    return reg


def run_hook_list(hooks: List[Callable], world, req, applied, *, errors: Optional[List[str]] = None):
    """
    Runs hooks safely. Hooks may return:
      - None (observe only)
      - list[dict] (effects to append)
    Any hook exception is captured and does NOT crash the request.
    """
    for h in list(hooks or []):
        try:
            out = h(world, req, applied)
            if out:
                for eff in out:
                    if isinstance(eff, dict):
                        applied.append(eff)
        except Exception as e:
            if errors is not None:
                errors.append(f"{getattr(h, '__name__', 'hook')}: {type(e).__name__}: {e}")
    return applied

# ---- Travel support (addon-provided transitions) ----
# Addons can register providers that return TravelEdge lists for a given location.
try:
    from .travel import TravelProvider
except Exception:
    TravelProvider = object  # type: ignore


def ensure_travel_registry(state) -> None:
    if not hasattr(state, "registry"):
        return
    reg = state.registry
    if not hasattr(reg, "travel_providers"):
        reg.travel_providers = []  # type: ignore[attr-defined]


def register_travel_provider(state, provider) -> None:
    ensure_travel_registry(state)
    state.registry.travel_providers.append(provider)
