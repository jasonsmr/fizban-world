"""render.py (v0.4)

Human-forward narrative rendering.

Design goals (from playtest + critique):
- Lattice voice: short, causal, not a system log; has mild personality and future-facing advice.
- Lore voice: archival shard only when something *commits* (facts/locks or big state shifts).
- Voices "talk" lightly: lattice can reference lore claims (without breaking uncertainty).

This module is drop-in compatible with simulator.py.v0_3+.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Any, Optional


# --- Utility ---


def _band_rank(b: str) -> int:
    order = {"abundant": 0, "stable": 1, "thin": 2, "scarce": 3, "critical": 4}
    return order.get(b, 1)


def derive_attention_heat(ws: Any) -> int:
    """Derived 0..100: how noticed you are.

    Heuristic (simple, stable):
    - tension carries most weight
    - noise_budget scarcity adds risk
    - hostile rumor adds risk
    """
    t = int(getattr(ws, "tension_index", 0) or 0)
    sb = getattr(ws, "scarcity_vector", {}) or {}
    rp = getattr(ws, "rumor_pressure", {}) or {}

    noise = _band_rank(sb.get("noise_budget", "stable"))
    mem = _band_rank(sb.get("memory_clarity", "stable"))
    rumor_peak = 0
    for _, v in rp.items():
        try:
            rumor_peak = max(rumor_peak, abs(int(v)))
        except Exception:
            continue

    heat = t + noise * 8 + rumor_peak * 6 + mem * 2
    return max(0, min(100, int(heat)))


# --- Friendly name maps (dev keys -> player-facing) ---


FACTION_NAMES = {
    "xi.faction.local": "the Witness Archive",
    "xi.faction.unknown": "someone you can't name",
}


SCARCITY_PHRASES = {
    "noise_budget": {
        "abundant": "you can make mistakes without being heard",
        "stable": "normal caution applies",
        "thin": "every sound carries",
        "scarce": "silence is precious",
        "critical": "one wrong noise will follow you",
    },
    "memory_clarity": {
        "abundant": "your recall is sharp",
        "stable": "you can trust yourself",
        "thin": "details slip",
        "scarce": "you keep second-guessing what you saw",
        "critical": "memory is unreliable right now",
    },
    "tools_basic": {
        "abundant": "you have what you need",
        "stable": "you can manage",
        "thin": "you’re improvising",
        "scarce": "you’re one tool short",
        "critical": "you’re working bare-handed",
    },
}


def _faction_label(fid: str) -> str:
    return FACTION_NAMES.get(fid, fid)


def _scarcity_sentence(axis: str, band: str) -> Optional[str]:
    d = SCARCITY_PHRASES.get(axis)
    if not d:
        return None
    return d.get(band)


def _diff_int(before: int, after: int) -> Optional[Tuple[int, int]]:
    if before == after:
        return None
    return before, after


def _collect_scarcity_deltas(ws_before: Any, ws_after: Any) -> List[Tuple[str, str, str]]:
    b = getattr(ws_before, "scarcity_vector", {}) or {}
    a = getattr(ws_after, "scarcity_vector", {}) or {}
    out = []
    for k in set(b) | set(a):
        bv = b.get(k)
        av = a.get(k)
        if bv != av:
            out.append((k, bv, av))
    # show most important first
    out.sort(key=lambda t: _band_rank(t[2] or "stable"), reverse=True)
    return out


def _collect_rumor_deltas(ws_before: Any, ws_after: Any) -> List[Tuple[str, int, int]]:
    b = getattr(ws_before, "rumor_pressure", {}) or {}
    a = getattr(ws_after, "rumor_pressure", {}) or {}
    out = []
    for k in set(b) | set(a):
        try:
            bv = int(b.get(k, 0))
            av = int(a.get(k, 0))
        except Exception:
            continue
        if bv != av:
            out.append((k, bv, av))
    # show biggest move first
    out.sort(key=lambda t: abs(t[2] - t[1]), reverse=True)
    return out


def lattice_voice(choice: Dict[str, Any], mutations: List[Dict[str, Any]], ws_before: Any, ws_after: Any) -> str:
    """Short, causal, human.

    Output structure:
    - what you did
    - what it cost (if any)
    - what changed (only the top 1-2 deltas)
    - what it implies now (heat / scarcity warning / rumor consequence)
    """

    label = choice.get("label") or choice.get("id") or "?"
    desc = (choice.get("text") or "").strip()

    parts: List[str] = []

    # 1) What you did
    if desc:
        parts.append(f"You went with **{label}** — {desc}")
    else:
        parts.append(f"You chose **{label}**.")

    # 2) What changed (tension + one more meaningful delta)
    t0 = int(getattr(ws_before, "tension_index", 0))
    t1 = int(getattr(ws_after, "tension_index", 0))
    td = _diff_int(t0, t1)
    if td:
        b, a = td
        if a > b:
            parts.append(f"The place tightens a notch (tension {b} → {a}).")
        else:
            parts.append(f"You bought yourself a breath (tension {b} → {a}).")

    sc = _collect_scarcity_deltas(ws_before, ws_after)
    rp = _collect_rumor_deltas(ws_before, ws_after)

    # prefer showing a scarcity shift if it worsened, otherwise rumor shift
    shown = 0
    for axis, bv, av in sc:
        if shown >= 1:
            break
        if _band_rank(av or "stable") > _band_rank(bv or "stable"):
            s = _scarcity_sentence(axis, av) or f"{axis} is now {av}"
            parts.append(f"Cost: {s}.")
            shown += 1

    if shown == 0 and rp:
        fid, bv, av = rp[0]
        who = _faction_label(fid)
        if av > bv:
            parts.append(f"Word moves toward {who} (rumor {bv:+d} → {av:+d}).")
        else:
            parts.append(f"You cool things with {who} (rumor {bv:+d} → {av:+d}).")

    # 3) What it implies now
    heat = derive_attention_heat(ws_after)
    if heat >= 80:
        parts.append("Right now you're *loud in the world's mind*. If you linger, something will answer.")
    elif heat >= 60:
        parts.append("You're being noticed. Not hunted yet — but watched.")

    # memory distortion cue
    mem = (getattr(ws_after, "scarcity_vector", {}) or {}).get("memory_clarity", "stable")
    if _band_rank(mem) >= 3:
        parts.append("And fair warning: your memory is getting slippery. Double-check what you 'know'.")

    return " ".join(parts)


def lore_voice(ws_before: Any, ws_after: Any) -> Optional[str]:
    """Return an archival shard only when new facts/locks arrive (or big threshold shift)."""
    bfacts = set(getattr(ws_before.flags, "facts", []) if getattr(ws_before, "flags", None) else [])
    afacts = set(getattr(ws_after.flags, "facts", []) if getattr(ws_after, "flags", None) else [])
    blocks = set(getattr(ws_before.flags, "locks", []) if getattr(ws_before, "flags", None) else [])
    alocks = set(getattr(ws_after.flags, "locks", []) if getattr(ws_after, "flags", None) else [])

    new_facts = sorted(list(afacts - bfacts))
    new_locks = sorted(list(alocks - blocks))

    if not new_facts and not new_locks:
        return None

    # Keep it short: 3-6 lines.
    lines: List[str] = []
    lines.append("[Archive Fragment — date uncertain]")
    if new_facts:
        f = new_facts[0]
        lines.append(f"It is recorded that: {f.replace('_', ' ').lower()}.")
    if new_locks:
        l = new_locks[0]
        lines.append(f"A seal was set: {l.replace('_', ' ').lower()}.")
    if len(new_facts) + len(new_locks) > 2:
        lines.append("Other notes exist, but the margins are torn.")
    lines.append("(Source reliability: mixed.)")
    return "\n".join(lines)
