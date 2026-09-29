from fastapi import APIRouter, Response, status

from app.api.deps import DBSession
from app.schemas.stream import MediaMTXAuthRequest
from app.services.stream_service import StreamService

router = APIRouter()


@router.post("/mediamtx/auth", include_in_schema=False)
async def mediamtx_auth(body: MediaMTXAuthRequest, db: DBSession) -> Response:
    """MediaMTX `authMethod: http` hook. 2xx = allow, anything else = deny.

    publish (edge push, RTSP or SRT): user = device_uuid, password = device key
    read / playback (browser):        short-lived stream token bound to the exact path
    """
    allowed = await StreamService(db).authorize_mediamtx(body)
    return Response(status_code=status.HTTP_200_OK if allowed else status.HTTP_401_UNAUTHORIZED)
