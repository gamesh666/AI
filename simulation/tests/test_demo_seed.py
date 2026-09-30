"""The seeder talks only to the public REST API; it must be idempotent."""

import uuid

from aivms_sim.seed import demo_seed
from aivms_sim.seed.demo_seed import SeedConfig, seed


class FakePlatform:
    """Minimal in-memory stand-in for the backend endpoints the seeder uses."""

    def __init__(self, preexisting_devices=()):
        self.sites, self.devices, self.cameras = [], [], []
        self.models = [{"id": "m1", "name": "yolov8n"}]
        for uuid_ in preexisting_devices:  # an edge that registered first
            self.devices.append({"id": str(uuid.uuid4()), "device_uuid": uuid_, "name": uuid_, "site_id": None})

    def __call__(self, method, path, body=None):
        route = path.split("?")[0]
        query = path.split("?")[1] if "?" in path else ""
        if route == "/health/ready":
            return {"status": "ok"}
        if route == "/auth/login":
            return {"access_token": "t"}
        if method == "GET":
            table = {"/sites": self.sites, "/devices": self.devices, "/cameras": self.cameras,
                     "/ai-models": self.models}[route]
            if route == "/cameras" and "edge_device_id=" in query:
                dev = query.split("edge_device_id=")[1].split("&")[0]
                table = [c for c in table if c["edge_device_id"] == dev]
            return {"items": table}
        if method == "POST":
            row = {"id": str(uuid.uuid4()), **body}
            {"/sites": self.sites, "/devices": self.devices, "/cameras": self.cameras}[route].append(row)
            return row
        if method == "PATCH":
            kind, id_ = route.strip("/").split("/")
            row = next(r for r in getattr(self, kind) if r["id"] == id_)
            row.update(body)
            return row
        raise AssertionError(f"unexpected {method} {path}")


def _run(monkeypatch, platform):
    monkeypatch.setattr(demo_seed.Api, "request", lambda self, method, path, body=None: platform(method, path, body))
    seed(SeedConfig(api_url="http://x", admin_username="admin", admin_password="p",
                    camera_rtsp_base="rtsp://sim-rtsp:8554", camera_username="admin", camera_password="c"))


def test_seed_creates_topology_and_is_idempotent(monkeypatch):
    platform = FakePlatform(preexisting_devices=["EDGE001"])
    _run(monkeypatch, platform)
    _run(monkeypatch, platform)
    assert sorted(s["code"] for s in platform.sites) == ["site01", "site02"]
    assert sorted(d["device_uuid"] for d in platform.devices) == ["EDGE001", "EDGE002"]
    assert sorted(c["code"] for c in platform.cameras) == ["CAM001", "CAM002", "CAM003", "CAM004"]
    site_of = {s["id"]: s["code"] for s in platform.sites}
    assert {d["device_uuid"]: site_of[d["site_id"]] for d in platform.devices} == {"EDGE001": "site01",
                                                                                   "EDGE002": "site02"}
    cam1 = next(c for c in platform.cameras if c["code"] == "CAM001")
    assert cam1["rtsp_url"] == "rtsp://sim-rtsp:8554/test/camera01" and cam1["ai_model_id"] == "m1"
