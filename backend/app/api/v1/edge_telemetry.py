"""Edge telemetry over HTTP (authenticated with X-Device-Key).

Same JSON as the MQTT topics, so an edge switches by changing where it sends, not what it sends. The device
identity comes from the key: `device_uuid` / `device_id` may be left out, and must match the key when given.
Errors are always {"detail": "<text>"}.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated, Any, TypeVar

from fastapi import APIRouter, Path, Request
from pydantic import BaseModel, ValidationError

from aivms_shared.payloads import CameraRuntimeStatus, DetectionEvent, EdgeLog, Heartbeat
from aivms_shared.payloads import DeviceStatus as DeviceStatusPayload
from app.api.deps import CurrentDevice, DBSession
from app.core.config import get_settings
from app.core.exceptions import DomainError, NotFoundError, PermissionDeniedError
from app.models.edge_device import EdgeDevice
from app.schemas.edge import EdgeHeartbeatAck, EdgeLogAck, EdgeLogBatchAck, EdgeLogRejected
from app.schemas.site import SLUG_PATTERN
from app.services import telemetry
from app.services.device_service import DeviceService
from app.services.edge_log_service import EdgeLogService
from app.services.event_service import EventService
from app.services.provisioning import UnprocessableError

router = APIRouter()

T = TypeVar("T", bound=BaseModel)

MAX_BODY_BYTES = 256 * 1024
MAX_LOGS_PER_REQUEST = 100


class PayloadTooLargeError(DomainError):
    status_code = 413


async def _json(request: Request) -> Any:
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise PayloadTooLargeError(f"request body too large (max {MAX_BODY_BYTES} bytes)")
    try:
        return json.loads(body)
    except ValueError:
        raise UnprocessableError("request body must be JSON") from None


def _object(data: Any) -> dict:
    if not isinstance(data, dict):
        raise UnprocessableError("request body must be a JSON object")
    return data


def _own(data: dict, field: str, value: str, what: str = "device") -> dict:
    """Fill the identity field from the key / path, or check that the given one matches it."""
    given = data.setdefault(field, value)
    if given != value:
        if what == "device":
            raise PermissionDeniedError(f"{field} '{given}' does not match the device key")
        raise UnprocessableError(f"{field} '{given}' does not match the URL ({value})")
    return data


def _validate(model: type[T], data: dict, what: str) -> T:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or 'body'}: {err['msg']}" for err in exc.errors()[:3]
        )
        raise UnprocessableError(f"invalid {what}: {problems}") from None


async def _heartbeat_ack(device: EdgeDevice) -> EdgeHeartbeatAck:
    return EdgeHeartbeatAck(
        config_version=await telemetry.config_version(device.device_uuid),
        commands=await telemetry.pop_commands(device.device_uuid),
        mqtt_enabled=get_settings().mqtt_edge_enabled,
        server_time=datetime.now(UTC),
    )


@router.post("/heartbeat", response_model=EdgeHeartbeatAck)
async def heartbeat(request: Request, device: CurrentDevice, db: DBSession) -> EdgeHeartbeatAck:
    """Same body as edge/{device}/heartbeat, every ~10 s. Without it for 30 s the device is shown offline.

    The answer carries what MQTT would push: pending commands and the config version.
    """
    data = _own(_object(await _json(request)), "device_uuid", device.device_uuid)
    hb = _validate(Heartbeat, data, "heartbeat")
    await DeviceService(db).ingest_heartbeat(hb, transport=telemetry.TRANSPORT_HTTP)
    return await _heartbeat_ack(device)


@router.post("/status", status_code=204)
async def status(request: Request, device: CurrentDevice, db: DBSession) -> None:
    """{"state": "online" | "offline"} — e.g. "offline" on a clean shutdown (MQTT used the Last Will for this)."""
    data = _own(_object(await _json(request)), "device_uuid", device.device_uuid)
    await DeviceService(db).ingest_status(_validate(DeviceStatusPayload, data, "status"))


@router.post("/cameras/{code}/status", status_code=204)
async def camera_status(
    request: Request,
    device: CurrentDevice,
    db: DBSession,
    code: Annotated[str, Path(pattern=SLUG_PATTERN)],
) -> None:
    """Same body as edge/{device}/cameras/{camera}/status."""
    data = _own(_object(await _json(request)), "camera_id", code, what="camera")
    payload = _validate(CameraRuntimeStatus, data, "camera status")
    if not await DeviceService(db).ingest_camera_status(device.device_uuid, payload):
        raise NotFoundError(f"camera '{code}' not found; announce it first with PUT /edge/cameras")


async def _store_log(service: EdgeLogService, device: EdgeDevice, item: Any) -> EdgeLogAck:
    data = _own(_object(item), "device_id", device.device_uuid)
    log = _validate(EdgeLog, data, "log")
    if reason := service.rejection(log):
        raise UnprocessableError(reason)
    if await service.ingest(log, device.device_uuid) is None:
        raise UnprocessableError("log not stored")
    return EdgeLogAck(event_id=log.event_id, camera_id=log.camera_id)


@router.post("/logs", response_model=EdgeLogAck | EdgeLogBatchAck)
async def logs(request: Request, device: CurrentDevice, db: DBSession) -> EdgeLogAck | EdgeLogBatchAck:
    """Same body as edge/{device}/logs (one object), or a JSON array of up to 100 of them.

    One object: 200 with its event_id, or an error. Array: 200 with what was accepted and what was not (by index);
    a rejected item never blocks the others. Re-sending an event_id updates that log (e.g. office.leave open ->
    returned). The camera goes in `camera_id`.
    """
    data = await _json(request)
    service = EdgeLogService(db)
    if not isinstance(data, list):
        return await _store_log(service, device, data)
    if len(data) > MAX_LOGS_PER_REQUEST:
        raise UnprocessableError(f"at most {MAX_LOGS_PER_REQUEST} logs per request")
    accepted: list[EdgeLogAck] = []
    rejected: list[EdgeLogRejected] = []
    for index, item in enumerate(data):
        try:
            accepted.append(await _store_log(service, device, item))
        except DomainError as exc:
            rejected.append(EdgeLogRejected(index=index, detail=exc.message))
    return EdgeLogBatchAck(accepted=accepted, rejected=rejected)


@router.post("/events", status_code=204)
async def events(request: Request, device: CurrentDevice, db: DBSession) -> None:
    """Detection event, same body as edge/{device}/cameras/{camera}/events (AIVMS edge-agent format)."""
    data = _own(_object(await _json(request)), "device_id", device.device_uuid)
    event = _validate(DetectionEvent, data, "event")
    if event.detections:
        await EventService(db).ingest(event, device.device_uuid)
