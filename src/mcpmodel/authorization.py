"""Authorization-envelope comparison used by both rules and learned models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from fnmatch import fnmatchcase
from typing import Any


@dataclass(frozen=True)
class AuthorizationGap:
    tool_gap: float
    action_gap: float
    resource_gap: float
    sink_gap: float
    temporal_gap: float
    cardinality_gap: float

    def as_features(self) -> dict[str, float]:
        return asdict(self)


def _matches(value: str | None, allowed: list[str]) -> bool:
    if value is None:
        return "<none>" in allowed or "*" in allowed
    return any(fnmatchcase(value, pattern) for pattern in allowed)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def compute_authorization_gap(
    authorization: dict[str, Any],
    call: dict[str, Any],
    *,
    normalized_tool: str | None = None,
    normalized_action: str | None = None,
    calls_used: int = 0,
) -> AuthorizationGap:
    """Return six explicit binary gap features; 1.0 means outside authorization."""
    tool = normalized_tool or str(call["tool"]).lower()
    action = normalized_action or str(call["action"]).lower()
    sink = call.get("sink")

    timestamp = call.get("timestamp")
    if timestamp is None:
        temporal_gap = 1.0
    else:
        moment = _parse_time(timestamp)
        temporal_gap = float(
            moment < _parse_time(authorization["valid_from"])
            or moment > _parse_time(authorization["valid_until"])
        )

    return AuthorizationGap(
        tool_gap=float(not _matches(tool, authorization["tools"])),
        action_gap=float(not _matches(action, authorization["actions"])),
        resource_gap=float(not _matches(str(call["resource"]), authorization["resources"])),
        sink_gap=float(not _matches(None if sink is None else str(sink), authorization["sinks"])),
        temporal_gap=temporal_gap,
        cardinality_gap=float(calls_used + 1 > int(authorization["max_calls"])),
    )
