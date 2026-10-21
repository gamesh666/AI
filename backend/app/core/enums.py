from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class DeviceStatus(StrEnum):
    PENDING = "pending"
    ONLINE = "online"
    OFFLINE = "offline"


class CameraStatus(StrEnum):
    """RTSP input status of a camera as reported by its edge device."""

    UNKNOWN = "unknown"
    CONNECTING = "connecting"
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"


class StreamStatus(StrEnum):
    """Status of the annotated stream pushed from the edge to MediaMTX."""

    OFFLINE = "offline"
    CONNECTING = "connecting"
    STREAMING = "streaming"
    ERROR = "error"


class AiStatus(StrEnum):
    IDLE = "idle"
    DISABLED = "disabled"
    LOADING = "loading"
    RUNNING = "running"
    ERROR = "error"


class StreamType(StrEnum):
    AI = "ai"
    ORIGINAL = "original"


# role hierarchy: a role satisfies every requirement at or below its level
ROLE_LEVEL: dict[UserRole, int] = {
    UserRole.VIEWER: 10,
    UserRole.OPERATOR: 20,
    UserRole.ADMIN: 30,
}
