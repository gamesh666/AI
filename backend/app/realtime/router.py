"""WebSocket endpoint: ws://<host>/ws?token=<access_token>[&types=detection.created,device.status]"""

from __future__ import annotations

import asyncio
import contextlib
import json

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.security import TOKEN_TYPE_ACCESS, TokenError, decode_token
from app.realtime.broadcaster import connection_manager
from app.realtime.connection_manager import Client
from app.realtime.messages import RealtimeEventType

router = APIRouter()

PING_INTERVAL_SECONDS = 25


def _parse_types(raw: str | None) -> set[RealtimeEventType]:
    if not raw:
        return set()
    valid = {e.value for e in RealtimeEventType}
    return {RealtimeEventType(t) for t in raw.split(",") if t in valid}


@router.websocket("/ws")
async def realtime_ws(
    websocket: WebSocket,
    token: str = Query(...),
    types: str | None = Query(default=None),
) -> None:
    try:
        claims = decode_token(token, TOKEN_TYPE_ACCESS)
    except TokenError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    client = Client(websocket=websocket, user_id=claims["sub"], subscriptions=_parse_types(types))
    await connection_manager.connect(client)

    async def keepalive() -> None:
        while True:
            await asyncio.sleep(PING_INTERVAL_SECONDS)
            await websocket.send_text(json.dumps({"type": "ping"}))

    ping_task = asyncio.create_task(keepalive())
    try:
        while True:
            # clients may change their subscription: {"action":"subscribe","types":[...]}
            msg = await websocket.receive_text()
            with contextlib.suppress(ValueError, AttributeError):
                body = json.loads(msg)
                if body.get("action") == "subscribe":
                    client.subscriptions = _parse_types(",".join(body.get("types", [])))
    except WebSocketDisconnect:
        pass
    finally:
        ping_task.cancel()
        await connection_manager.disconnect(client)
