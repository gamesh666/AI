"""RTSP push over TCP: rtsp://<device_uuid>:<device_key>@MEDIA:8554/ai/<site>/<device>/<camera>"""

from __future__ import annotations

from urllib.parse import quote, urlsplit, urlunsplit

from agent.core.backoff import Backoff
from agent.streaming.publisher import EncoderFactory, EncoderPublisher
from agent.video.encoder import EncoderSettings


def build_rtsp_url(base_url: str, path: str, username: str | None, password: str | None) -> str:
    parts = urlsplit(base_url.rstrip("/"))
    netloc = parts.netloc
    if username:
        netloc = f"{quote(username, safe='')}:{quote(password or '', safe='')}@{netloc}"
    return urlunsplit(parts._replace(netloc=netloc, path=f"{parts.path}/{path.strip('/')}"))


class RTSPPublisher(EncoderPublisher):
    output_format = "rtsp"

    def __init__(self, base_url: str, path: str, username: str | None, password: str | None,
                 settings: EncoderSettings, encoder_factory: EncoderFactory, backoff: Backoff | None = None,
                 **kwargs) -> None:
        super().__init__(
            target_url=build_rtsp_url(base_url, path, username, password),
            display_url=build_rtsp_url(base_url, path, None, None),
            settings=settings,
            encoder_factory=encoder_factory,
            backoff=backoff,
            **kwargs,
        )

    def output_args(self) -> list[str]:
        return ["-rtsp_transport", "tcp"]
