"""Import every model so Base.metadata is complete (Alembic autogenerate relies on this)."""

from app.models.ai_model import AIModel
from app.models.camera import Camera
from app.models.detection_event import DetectionEvent
from app.models.edge_device import EdgeDevice
from app.models.site import Site
from app.models.user import RefreshToken, User

__all__ = ["AIModel", "Camera", "DetectionEvent", "EdgeDevice", "RefreshToken", "Site", "User"]
