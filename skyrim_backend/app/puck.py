from __future__ import annotations

from typing import List, Tuple

from .models import DecisionOut, SkyrimEvent
from .state import WORLD


def _has(tags: List[str], want: str) -> bool:
    return any(t.lower() == want.lower() for t in tags)


def decide(event: SkyrimEvent) -> DecisionOut:
    WORLD.tick += 1

    actor = event.target or "Puck"
    WORLD.touch(event.actor, event.location or None)
    WORLD.touch(actor, event.location or None)

    # baseline
    decision = "TALK"
    confidence = 0.55
    reasons: List[str] = ["social_default"]
    say = "So… what are we doing next?"

    # Dialogue hooks
    if event.t.value == "DIALOGUE":
        reasons.append("dialogue")
        line = str(event.payload.get("line", "")).lower()

        if _has(event.tags, "gossip") or "news" in line or "heard" in line:
            decision = "GOSSIP"
            confidence = min(0.9, 0.55 + 0.2 * event.intensity)
            reasons.append("gossip_hook")
            say = "Oh, I’ve heard *things*… but do we trust the source?"

        if "lying" in line or "betray" in line:
            decision = "SUSPICION"
            confidence = min(0.95, 0.6 + 0.25 * event.intensity)
            reasons.append("betrayal_probe")
            say = "Mmm. Names are dangerous. Give me a hint… and a reason."

    return DecisionOut(
        actor=actor,
        decision=decision,
        confidence=float(confidence),
        reason_tags=reasons,
        say=say,
        metadata={"world_tick": WORLD.tick, "input_event_id": event.event_id},
    )
