from __future__ import annotations

import re
import time
import traceback
from dataclasses import is_dataclass, asdict
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Tuple, Union


# -----------------------------
# Basic shape helpers
# -----------------------------
def is_mapping(x: Any) -> bool:
    return isinstance(x, Mapping)


def is_mutable_mapping(x: Any) -> bool:
    return isinstance(x, MutableMapping)


def get_attr_or_key(obj: Any, name: str, default: Any = None) -> Any:
    """
    Compatibility accessor:
      - obj.name (attribute)
      - obj[name] (mapping key)
    """
    if obj is None:
        return default

    # attribute first
    try:
        if hasattr(obj, name):
            return getattr(obj, name)
    except Exception:
        pass

    # mapping key
    try:
        if isinstance(obj, Mapping) and name in obj:
            return obj.get(name, default)
    except Exception:
        pass

    return default


def set_attr_or_key(obj: Any, name: str, value: Any) -> bool:
    """
    Compatibility setter:
      - setattr(obj, name, value) if possible
      - obj[name] = value if mapping
    Returns True if set, False otherwise.
    """
    if obj is None:
        return False

    # try attribute
    try:
        # if it already has the attr OR it's not a mapping, setattr is usually safe
        if hasattr(obj, name) or not isinstance(obj, Mapping):
            setattr(obj, name, value)
            return True
    except Exception:
        pass

    # try mapping
    try:
        if isinstance(obj, MutableMapping):
            obj[name] = value
            return True
    except Exception:
        pass

    return False


# -----------------------------
# Pydantic / model compatibility
# -----------------------------
def safe_model_dump(x: Any) -> Any:
    """
    Main entrypoint used by main.py/addons/etc.
    - pydantic v2: .model_dump()
    - pydantic v1: .dict()
    - mapping: dict(x)
    - dataclass: asdict
    - object: vars(x)
    """
    if x is None:
        return None
    if isinstance(x, Mapping):
        return dict(x)
    if is_dataclass(x):
        try:
            return asdict(x)
        except Exception:
            pass

    md = getattr(x, "model_dump", None)
    if callable(md):
        try:
            return md()
        except Exception:
            return x

    dct = getattr(x, "dict", None)
    if callable(dct):
        try:
            return dct()
        except Exception:
            return x

    try:
        return dict(vars(x))
    except Exception:
        return x


def maybe_model_dump(x: Any) -> Any:
    """
    Backwards-compatible alias (some files used this name).
    """
    return safe_model_dump(x)


def model_to_dict(x: Any) -> Dict[str, Any]:
    """
    Normalize model-like objects into a plain dict.
    Always returns a dict (possibly empty).
    """
    v = safe_model_dump(x)
    if v is None:
        return {}
    if isinstance(v, Mapping):
        return dict(v)
    # if safe_model_dump returned original object
    if isinstance(x, Mapping):
        return dict(x)
    try:
        return dict(vars(x))
    except Exception:
        return {}


# -----------------------------
# World meta helpers
# -----------------------------
def _ensure_world_meta_container(world: Any) -> MutableMapping[str, Any]:
    """
    Ensure world.meta (or world["meta"]) exists and is a mutable mapping.
    """
    meta = get_attr_or_key(world, "meta", None)
    if isinstance(meta, MutableMapping):
        return meta

    # if meta exists but isn't mutable, overwrite with {}
    meta_obj: Dict[str, Any] = {}
    set_attr_or_key(world, "meta", meta_obj)
    meta2 = get_attr_or_key(world, "meta", None)
    if isinstance(meta2, MutableMapping):
        return meta2

    # last resort: if the world itself is a mapping, store under key
    if isinstance(world, MutableMapping):
        world["meta"] = {}
        return world["meta"]

    # absolute fallback (won't persist, but prevents crashes)
    return {}  # type: ignore[return-value]


def world_get_meta(world: Any, key: str, default: Any = None) -> Any:
    meta = _ensure_world_meta_container(world)
    try:
        return meta.get(key, default)
    except Exception:
        return default


def world_set_meta(world: Any, key: str, value: Any) -> None:
    meta = _ensure_world_meta_container(world)
    try:
        meta[key] = value
        return
    except Exception:
        pass
    # if meta is non-writable for some reason, try replacing
    set_attr_or_key(world, "meta", {key: value})


# -----------------------------
# Dict/list field helpers (used by logic.py)
# -----------------------------
def ensure_dict_field(obj: Any, field: str) -> Dict[str, Any]:
    """
    Ensure obj.<field> (or obj[field]) exists and is a dict.
    Returns the dict.
    """
    cur = get_attr_or_key(obj, field, None)
    if isinstance(cur, dict):
        return cur
    new: Dict[str, Any] = {}
    set_attr_or_key(obj, field, new)
    cur2 = get_attr_or_key(obj, field, None)
    return cur2 if isinstance(cur2, dict) else new


def ensure_list_field(obj: Any, field: str) -> List[Any]:
    """
    Ensure obj.<field> (or obj[field]) exists and is a list.
    """
    cur = get_attr_or_key(obj, field, None)
    if isinstance(cur, list):
        return cur
    new: List[Any] = []
    set_attr_or_key(obj, field, new)
    cur2 = get_attr_or_key(obj, field, None)
    return cur2 if isinstance(cur2, list) else new


def find_first_mapping_field(
    obj: Any, candidates: Iterable[str]
) -> Tuple[Optional[MutableMapping[str, Any]], Optional[str]]:
    """
    Look for the first field in candidates that exists on obj (attr or key) and is a mapping.
    Returns (mapping, field_name) or (None, None).
    """
    for name in candidates:
        val = get_attr_or_key(obj, name, None)
        if isinstance(val, MutableMapping):
            return val, name
        if isinstance(val, Mapping):
            # not mutable, but still usable read-only; return dict wrapper
            return dict(val), name  # type: ignore[return-value]
    return None, None


# -----------------------------
# Time / tick helpers
# -----------------------------
def now_ts() -> float:
    return time.time()


def bump_tick(world: Any, delta: int = 1) -> int:
    """
    Increment world.tick (attr or key). Returns new tick int.
    """
    tick = get_attr_or_key(world, "tick", 0)
    try:
        t = int(tick)
    except Exception:
        t = 0
    t += int(delta)
    set_attr_or_key(world, "tick", t)
    return t


# -----------------------------
# Version helpers (used by addons.py)
# -----------------------------
_VERSION_RE = re.compile(r"^\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-+].*)?\s*$")


def _parse_version(v: str) -> Tuple[int, int, int]:
    """
    Loose semver-ish parse:
      '0.3.0' -> (0,3,0)
      '1.2'   -> (1,2,0)
      'v2.0'  -> (2,0,0)
    Non-matching strings -> (0,0,0)
    """
    if not v:
        return (0, 0, 0)
    m = _VERSION_RE.match(v)
    if not m:
        return (0, 0, 0)
    major = int(m.group(1) or 0)
    minor = int(m.group(2) or 0)
    patch = int(m.group(3) or 0)
    return (major, minor, patch)


def _cmp(a: Tuple[int, int, int], b: Tuple[int, int, int]) -> int:
    return (a > b) - (a < b)


def version_satisfies(current: str, requirement: str) -> bool:
    """
    Minimal requirement checker for addon manifests.
    Supports:
      - ">=0.1.0", ">0.2.0", "<=1.0.0", "==0.3.0", "!=0.3.0"
      - bare "0.3.0" treated as ">=0.3.0" (pragmatic)
      - empty/None requirement -> True
    """
    if not requirement:
        return True

    req = requirement.strip()

    # allow comma-separated constraints: ">=0.1.0,<1.0.0"
    parts = [p.strip() for p in req.split(",") if p.strip()]
    if not parts:
        return True

    cur_v = _parse_version(current)

    for p in parts:
        op = None
        ver = p

        for candidate in ("<=", ">=", "==", "!=", "<", ">"):
            if p.startswith(candidate):
                op = candidate
                ver = p[len(candidate):].strip()
                break

        if op is None:
            # bare version: treat as >=
            op = ">="
            ver = p.strip()

        req_v = _parse_version(ver)
        c = _cmp(cur_v, req_v)

        if op == ">=" and not (c >= 0):
            return False
        if op == ">" and not (c > 0):
            return False
        if op == "<=" and not (c <= 0):
            return False
        if op == "<" and not (c < 0):
            return False
        if op == "==" and not (c == 0):
            return False
        if op == "!=" and not (c != 0):
            return False

    return True


# -----------------------------
# Error formatting (API)
# -----------------------------
def format_exception_payload(exc: Exception, trace_id: str = "no-trace", debug: bool = False) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "ok": False,
        "trace_id": trace_id,
        "error": {
            "type": type(exc).__name__,
            "message": str(exc),
        },
    }
    if debug:
        payload["error"]["traceback"] = traceback.format_exc()
    return payload


# -----------------------------
# Safe call wrapper (hooks / addons)
# -----------------------------
def safe_call(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Tuple[Any, Optional[str]]:
    """
    Call fn safely. Returns (result, error_string_or_none).
    """
    try:
        return fn(*args, **kwargs), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
