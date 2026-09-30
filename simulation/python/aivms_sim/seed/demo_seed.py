"""Creates the demo sites / edge devices / cameras through the platform's public REST API.

Idempotent: existing objects are found by their IDs and updated, never duplicated. The edge agents may
register before or after this runs — both orders converge to the same state.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from aivms_sim.seed.topology import TOPOLOGY, DemoCamera, DemoDevice, DemoSite

logger = logging.getLogger("demo-seed")


@dataclass(frozen=True)
class SeedConfig:
    api_url: str
    admin_username: str
    admin_password: str
    camera_rtsp_base: str  # e.g. rtsp://sim-rtsp:8554
    camera_username: str
    camera_password: str
    model_name: str = "yolov8n"
    stream_resolution: str | None = "1280x720"
    stream_fps: int = 25
    inference_fps: float = 5.0
    bitrate: str = "2M"
    gop_size: int = 50

    @classmethod
    def from_env(cls) -> SeedConfig:
        def req(name: str) -> str:
            value = os.environ.get(name)
            if not value:
                raise SystemExit(f"{name} is required")
            return value

        return cls(
            api_url=os.environ.get("DEMO_API_URL", "http://backend:8000/api/v1").rstrip("/"),
            admin_username=os.environ.get("DEMO_ADMIN_USERNAME", "admin"),
            admin_password=req("DEMO_ADMIN_PASSWORD"),
            camera_rtsp_base=os.environ.get("DEMO_CAMERA_RTSP_BASE", "rtsp://sim-rtsp:8554").rstrip("/"),
            camera_username=os.environ.get("DEMO_CAMERA_USERNAME", "admin"),
            camera_password=req("DEMO_CAMERA_PASSWORD"),
            model_name=os.environ.get("DEMO_MODEL_NAME", "yolov8n"),
            stream_resolution=os.environ.get("DEMO_STREAM_RESOLUTION", "1280x720") or None,
            stream_fps=int(os.environ.get("DEMO_STREAM_FPS", "25")),
            inference_fps=float(os.environ.get("DEMO_INFERENCE_FPS", "5")),
            bitrate=os.environ.get("DEMO_STREAM_BITRATE", "2M"),
            gop_size=int(os.environ.get("DEMO_GOP_SIZE", "50")),
        )


class ApiError(Exception):
    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"HTTP {status}: {body[:200]}")
        self.status = status


class Api:
    def __init__(self, base: str) -> None:
        self.base = base
        self.token: str | None = None

    def request(self, method: str, path: str, body: dict | None = None) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"{self.base}{path}", data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            raise ApiError(exc.code, exc.read().decode(errors="replace")) from exc
        return json.loads(raw) if raw else None

    def items(self, path: str) -> list[dict]:
        sep = "&" if "?" in path else "?"
        return self.request("GET", f"{path}{sep}page_size=500")["items"]


def wait_for_backend(api: Api, timeout: float = 300) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            api.request("GET", "/health/ready")
            return
        except Exception as exc:
            if time.monotonic() > deadline:
                raise SystemExit(f"backend not ready: {exc}") from exc
            logger.info("waiting for backend (%s)", exc)
            time.sleep(3)


def ensure_site(api: Api, site: DemoSite) -> dict:
    for s in api.items("/sites"):
        if s["code"] == site.code:
            return s
    logger.info("creating site %s", site.code)
    return api.request("POST", "/sites", {"name": site.name, "code": site.code, "address": site.address,
                                          "description": "Created by the simulation demo seeder"})


def ensure_device(api: Api, device: DemoDevice, site_id: str) -> dict:
    for d in api.items("/devices"):
        if d["device_uuid"] == device.device_uuid:
            if d["site_id"] != site_id or d["name"] != device.name:
                logger.info("updating device %s", device.device_uuid)
                return api.request("PATCH", f"/devices/{d['id']}", {"name": device.name, "site_id": site_id})
            return d
    logger.info("creating device %s", device.device_uuid)
    # the returned API key is discarded: the simulated edge self-registers with the provisioning token
    try:
        return api.request("POST", "/devices", {"device_uuid": device.device_uuid, "name": device.name,
                                                "site_id": site_id})
    except ApiError as exc:
        if exc.status != 409:  # the edge registered in between
            raise
        return ensure_device(api, device, site_id)


def camera_body(cfg: SeedConfig, camera: DemoCamera, device_id: str, model_id: str | None) -> dict:
    return {
        "edge_device_id": device_id,
        "code": camera.code,
        "name": camera.name,
        # an ordinary RTSP camera URL — the fake camera is indistinguishable from a real one
        "rtsp_url": f"{cfg.camera_rtsp_base}/{camera.rtsp_path}",
        "rtsp_username": cfg.camera_username,
        "rtsp_password": cfg.camera_password,
        "enabled": True,
        "ai_enabled": True,
        "ai_model_id": model_id,
        "stream_enabled": True,
        "annotated_stream_enabled": True,
        "original_stream_enabled": False,
        "resolution": cfg.stream_resolution,
        "stream_fps": cfg.stream_fps,
        "inference_fps": cfg.inference_fps,
        "bitrate": cfg.bitrate,
        "gop_size": cfg.gop_size,
    }


def ensure_camera(api: Api, cfg: SeedConfig, camera: DemoCamera, device_id: str, model_id: str | None) -> None:
    existing = {c["code"]: c for c in api.items(f"/cameras?edge_device_id={device_id}")}
    body = camera_body(cfg, camera, device_id, model_id)
    if camera.code in existing:
        logger.info("updating camera %s", camera.code)
        api.request("PATCH", f"/cameras/{existing[camera.code]['id']}", body)
    else:
        logger.info("creating camera %s", camera.code)
        api.request("POST", "/cameras", body)


def seed(cfg: SeedConfig) -> None:
    api = Api(cfg.api_url)
    wait_for_backend(api)
    api.token = api.request("POST", "/auth/login",
                            {"username": cfg.admin_username, "password": cfg.admin_password})["access_token"]
    model_id = next((m["id"] for m in api.items("/ai-models") if m["name"] == cfg.model_name), None)
    for site in TOPOLOGY:
        site_row = ensure_site(api, site)
        for device in site.devices:
            device_row = ensure_device(api, device, site_row["id"])
            for camera in device.cameras:
                ensure_camera(api, cfg, camera, device_row["id"], model_id)
    logger.info("demo topology ready: %d sites, %d edge devices, %d cameras", len(TOPOLOGY),
                sum(len(s.devices) for s in TOPOLOGY), sum(len(d.cameras) for s in TOPOLOGY for d in s.devices))
