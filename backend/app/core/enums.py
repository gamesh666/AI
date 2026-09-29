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
    UNKNOWN = "unknown"
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"


# role hierarchy: a role satisfies every requirement at or below its level
ROLE_LEVEL: dict[UserRole, int] = {
    UserRole.VIEWER: 10,
    UserRole.OPERATOR: 20,
    UserRole.ADMIN: 30,
}
