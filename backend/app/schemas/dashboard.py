from pydantic import BaseModel


class DashboardSummary(BaseModel):
    online_devices: int
    offline_devices: int
    pending_devices: int
    camera_count: int
    active_camera_count: int
    events_today: int
