"""Import every model so Base.metadata is complete (Alembic autogenerate relies on this)."""

from app.models.ai_model import AIModel
from app.models.camera import Camera
from app.models.edge_device import EdgeDevice
from app.models.edge_log import EdgeLog
from app.models.owner import EdgeDeviceAudit, Owner, ProvisioningToken
from app.models.report import DeviceReport
from app.models.site import Site
from app.models.user import RefreshToken, User

__all__ = [
    "AIModel",
    "Camera",
    "DeviceReport",
    "EdgeDevice",
    "EdgeDeviceAudit",
    "EdgeLog",
    "Owner",
    "ProvisioningToken",
    "RefreshToken",
    "Site",
    "User",
]
