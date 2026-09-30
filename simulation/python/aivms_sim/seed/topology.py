"""Demo topology: 2 sites, 2 simulated edge devices, 4 fake cameras.

    site01  Demo Site A ── EDGE001 ── CAM001 (test/camera01), CAM002 (test/camera02)
    site02  Demo Site B ── EDGE002 ── CAM003 (test/camera03), CAM004 (test/camera04)

Cameras are identified by site / device / camera ID. Their RTSP address (the fake-camera server on the
simulated camera LAN) is edge-side data, exactly like a real IP camera's address.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DemoCamera:
    code: str
    name: str
    rtsp_path: str  # path on the simulated camera LAN RTSP server


@dataclass(frozen=True)
class DemoDevice:
    device_uuid: str
    name: str
    cameras: tuple[DemoCamera, ...]


@dataclass(frozen=True)
class DemoSite:
    code: str
    name: str
    address: str
    devices: tuple[DemoDevice, ...] = field(default_factory=tuple)


TOPOLOGY: tuple[DemoSite, ...] = (
    DemoSite(
        code="site01",
        name="Demo Site A",
        address="Simulated — Taipei",
        devices=(
            DemoDevice("EDGE001", "Edge Gateway 001", (
                DemoCamera("CAM001", "Main Entrance", "test/camera01"),
                DemoCamera("CAM002", "Parking Lot", "test/camera02"),
            )),
        ),
    ),
    DemoSite(
        code="site02",
        name="Demo Site B",
        address="Simulated — Taichung",
        devices=(
            DemoDevice("EDGE002", "Edge Gateway 002", (
                DemoCamera("CAM003", "Construction Yard", "test/camera03"),
                DemoCamera("CAM004", "Loading Dock", "test/camera04"),
            )),
        ),
    ),
)
