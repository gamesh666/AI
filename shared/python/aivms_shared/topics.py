"""MQTT topic layout.

Edge -> Server:
    edge/{device_id}/heartbeat
    edge/{device_id}/status
    edge/{device_id}/events
    edge/{device_id}/cameras/{camera_id}/events
    edge/{device_id}/cameras/{camera_id}/status

Server -> Edge:
    server/{device_id}/command
    server/{device_id}/config
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

EDGE_PREFIX = "edge"
SERVER_PREFIX = "server"


class TopicKind(StrEnum):
    HEARTBEAT = "heartbeat"
    STATUS = "status"
    DEVICE_EVENTS = "device_events"
    CAMERA_EVENTS = "camera_events"
    CAMERA_STATUS = "camera_status"
    COMMAND = "command"
    CONFIG = "config"


# ---- builders -------------------------------------------------------------


def heartbeat(device_id: str) -> str:
    return f"{EDGE_PREFIX}/{device_id}/heartbeat"


def status(device_id: str) -> str:
    return f"{EDGE_PREFIX}/{device_id}/status"


def device_events(device_id: str) -> str:
    return f"{EDGE_PREFIX}/{device_id}/events"


def camera_events(device_id: str, camera_id: str) -> str:
    return f"{EDGE_PREFIX}/{device_id}/cameras/{camera_id}/events"


def camera_status(device_id: str, camera_id: str) -> str:
    return f"{EDGE_PREFIX}/{device_id}/cameras/{camera_id}/status"


def command(device_id: str) -> str:
    return f"{SERVER_PREFIX}/{device_id}/command"


def config(device_id: str) -> str:
    return f"{SERVER_PREFIX}/{device_id}/config"


# ---- subscription filters ---------------------------------------------------

SERVER_SUBSCRIPTIONS: dict[TopicKind, str] = {
    TopicKind.HEARTBEAT: f"{EDGE_PREFIX}/+/heartbeat",
    TopicKind.STATUS: f"{EDGE_PREFIX}/+/status",
    TopicKind.DEVICE_EVENTS: f"{EDGE_PREFIX}/+/events",
    TopicKind.CAMERA_EVENTS: f"{EDGE_PREFIX}/+/cameras/+/events",
    TopicKind.CAMERA_STATUS: f"{EDGE_PREFIX}/+/cameras/+/status",
}


def edge_subscriptions(device_id: str) -> list[str]:
    return [command(device_id), config(device_id)]


def shared(filter_: str, group: str | None) -> str:
    """Wrap a filter in an MQTT v5 shared subscription (supported by Mosquitto 2.x and EMQX)."""
    return f"$share/{group}/{filter_}" if group else filter_


# ---- parsing ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ParsedTopic:
    kind: TopicKind
    device_id: str
    camera_id: str | None = None


def parse(topic: str) -> ParsedTopic | None:
    """Parse a concrete topic into its kind and identifiers. Returns None if unknown."""
    parts = topic.split("/")
    if len(parts) < 3 or not parts[1]:
        return None
    prefix, device_id = parts[0], parts[1]

    if prefix == EDGE_PREFIX:
        if len(parts) == 3:
            kind = {
                "heartbeat": TopicKind.HEARTBEAT,
                "status": TopicKind.STATUS,
                "events": TopicKind.DEVICE_EVENTS,
            }.get(parts[2])
            return ParsedTopic(kind, device_id) if kind else None
        if len(parts) == 5 and parts[2] == "cameras" and parts[3]:
            kind = {"events": TopicKind.CAMERA_EVENTS, "status": TopicKind.CAMERA_STATUS}.get(parts[4])
            return ParsedTopic(kind, device_id, parts[3]) if kind else None
        return None

    if prefix == SERVER_PREFIX and len(parts) == 3:
        kind = {"command": TopicKind.COMMAND, "config": TopicKind.CONFIG}.get(parts[2])
        return ParsedTopic(kind, device_id) if kind else None

    return None
