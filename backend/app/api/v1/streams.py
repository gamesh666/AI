import uuid

from fastapi import APIRouter, Response, status

from app.api.deps import DBSession, ViewerUser
from app.schemas.stream import MediaMTXAuthRequest, StreamInfo
from app.services.stream_service import StreamService

router = APIRouter()


@router.get("/{camera_id}", response_model=StreamInfo)
async def get_stream(camera_id: uuid.UUID, db: DBSession, user: ViewerUser) -> StreamInfo:
    """WebRTC (WHEP) + HLS URLs and a short-lived stream token for one camera."""
    return await StreamService(db).stream_info(camera_id, user)


@router.post("/mediamtx/auth", include_in_schema=False)
async def mediamtx_auth(body: MediaMTXAuthRequest, db: DBSession) -> Response:
    """MediaMTX `authMethod: http` hook. 2xx = allow, anything else = deny."""
    allowed = await StreamService(db).authorize_mediamtx(body)
    return Response(status_code=status.HTTP_200_OK if allowed else status.HTTP_401_UNAUTHORIZED)
