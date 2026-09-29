"""SRT push (recommended across the Internet: loss recovery, latency control, optional encryption).

MediaMTX stream id format: publish:<path>:<user>:<pass>
  srt://MEDIA:8890?streamid=publish:ai/site01/edge01/cam01:edge01:<device_key>&pkt_size=1316
"""

from __future__ import annotations

from urllib.parse import urlsplit

from agent.core.backoff import Backoff
from agent.streaming.publisher import EncoderFactory, EncoderPublisher
from agent.video.encoder import EncoderSettings


def build_srt_url(base_url: str, path: str, username: str | None, password: str | None,
                  latency_ms: int = 200, passphrase: str | None = None) -> str:
    parts = urlsplit(base_url)
    stream_id = f"publish:{path.strip('/')}"
    if username:
        stream_id += f":{username}:{password or ''}"
    url = f"srt://{parts.netloc}?streamid={stream_id}&pkt_size=1316&latency={latency_ms * 1000}"
    if passphrase:
        url += f"&passphrase={passphrase}"
    return url


class SRTPublisher(EncoderPublisher):
    output_format = "mpegts"

    def __init__(self, base_url: str, path: str, username: str | None, password: str | None,
                 settings: EncoderSettings, encoder_factory: EncoderFactory, backoff: Backoff | None = None,
                 latency_ms: int = 200, **kwargs) -> None:
        super().__init__(
            target_url=build_srt_url(base_url, path, username, password, latency_ms),
            display_url=f"srt://{urlsplit(base_url).netloc}/{path.strip('/')}",
            settings=settings,
            encoder_factory=encoder_factory,
            backoff=backoff,
            **kwargs,
        )
