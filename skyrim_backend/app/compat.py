from __future__ import annotations

import dataclasses
import json
import time
import traceback
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple


def now_ts() -> float:
    return time.time()


def is_mapping(x: Any) -> bool:
    return isinstance(x, Mapping)


def get_attr_or_key(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def set_attr_or_key(obj: Any, name: str, value: Any) -> None:
    if obj is None:
        return
    if isinstance(obj, dict):
        obj[name] = value
        return
    try:
        setattr(obj, name, value)
    except Exception:
        # Some pydantic/dataclass/frozen objects may not allow setattr; ignore.
        pass


def model_to_dict(obj: Any) -> Any:
    """
    Convert pydantic v2/v1, dataclasses, dicts to plain JSON-friendly python.
    """
    if obj is None:
        return None

    # dict already
    if isinstance(obj, dict):
        return obj

    # pydantic v2
    md = getattr(obj, "model_dump", None)
    if callable(md):
        try:
            return md()
        except TypeError:
            return md()

    # pydantic v1
    d = getattr(obj, "dict", None)
    if callable(d):
        try:
            return d()
        except TypeError:
            return d()

    # dataclass
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)

    # generic object
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)

    return obj


def safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, default=model_to_dict)
    except Exception:
        return json.dumps({"unserializable": str(type(obj))}, ensure_ascii=False)


def bump_tick(world: Any, delta: int = 1) -> int:
    tick = get_attr_or_key(world, "tick", 0)
    try:
        tick_i = int(tick)
    except Exception:
        tick_i = 0
    tick_i += int(delta)
    set_attr_or_key(world, "tick", tick_i)
    return tick_i


def find_first_mapping_field(
    obj: Any,
    candidates: Iterable[str],
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Find the first attribute/key that looks like a dict-like mapping.
    Returns (field_name, mapping) or None.
    """
    for name in candidates:
        val = get_attr_or_key(obj, name, None)
        if isinstance(val, dict):
            return name, val
        # accept Mapping but coerce to dict only if safe
        if isinstance(val, Mapping):
            return name, dict(val)
    return None


def ensure_dict_field(obj: Any, name: str) -> Dict[str, Any]:
    cur = get_attr_or_key(obj, name, None)
    if isinstance(cur, dict):
        return cur
    if isinstance(cur, Mapping):
        d = dict(cur)
        set_attr_or_key(obj, name, d)
        return d
    d = {}
    set_attr_or_key(obj, name, d)
    return d


def format_exception_payload(exc: BaseException, trace_id: str, debug: bool) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "ok": False,
        "trace_id": trace_id,
        "error": {
            "type": exc.__class__.__name__,
            "message": str(exc),
        },
    }
    if debug:
        payload["error"]["traceback"] = traceback.format_exc()
    return payload
