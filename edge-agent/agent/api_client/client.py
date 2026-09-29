"""REST client for the central backend (device-facing API)."""

from __future__ import annotations

import logging
import time

import httpx

from agent import __version__
from agent.config.models import DeviceConfig, PresignedUpload

logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class BackendClient:
    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"User-Agent": f"aivms-edge-agent/{__version__}"},
        )
        self._device_key: str | None = None

    def set_device_key(self, key: str) -> None:
        self._device_key = key

    def close(self) -> None:
        self._http.close()

    # ---- helpers ------------------------------------------------------------

    def _request(self, method: str, path: str, *, retries: int = 3, **kwargs) -> httpx.Response:
        headers = kwargs.pop("headers", {})
        if self._device_key:
            headers.setdefault("X-Device-Key", self._device_key)
        delay = 1.0
        for attempt in range(1, retries + 1):
            try:
                resp = self._http.request(method, path, headers=headers, **kwargs)
            except httpx.TransportError as exc:
                if attempt == retries:
                    raise ApiError(f"{method} {path} failed: {exc}") from exc
                logger.warning("%s %s transport error (%s), retry %d", method, path, exc, attempt)
                time.sleep(delay)
                delay *= 2
                continue
            if resp.status_code >= 500 and attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue
            if resp.is_error:
                raise ApiError(f"{method} {path} -> {resp.status_code}: {resp.text[:200]}", resp.status_code)
            return resp
        raise ApiError(f"{method} {path} exhausted retries")

    # ---- endpoints ------------------------------------------------------------

    def register(self, provisioning_token: str, device_uuid: str, **info) -> str:
        resp = self._request(
            "POST",
            "/edge/register",
            json={"device_uuid": device_uuid, "agent_version": __version__, **info},
            headers={"X-Provisioning-Token": provisioning_token},
        )
        return resp.json()["api_key"]

    def get_config(self) -> DeviceConfig:
        return DeviceConfig.model_validate(self._request("GET", "/edge/config").json())

    def presign_snapshot(self, camera_id: str, content_type: str = "image/jpeg") -> PresignedUpload:
        resp = self._request(
            "POST", "/edge/snapshots/presign", json={"camera_id": camera_id, "content_type": content_type}
        )
        return PresignedUpload.model_validate(resp.json())

    def upload(self, url: str, data: bytes, content_type: str) -> None:
        # presigned URL: no API headers, plain PUT
        resp = httpx.put(url, content=data, headers={"Content-Type": content_type}, timeout=15.0)
        if resp.is_error:
            raise ApiError(f"snapshot upload failed: {resp.status_code} {resp.text[:200]}", resp.status_code)
