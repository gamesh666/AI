from __future__ import annotations

from dataclasses import dataclass

from agent.streaming.publisher import EncoderFactory, StreamPublisher
from agent.streaming.rtsp_publisher import RTSPPublisher
from agent.streaming.srt_publisher import SRTPublisher
from agent.video.encoder import EncoderSettings


@dataclass(frozen=True, slots=True)
class PublishEndpoint:
    protocol: str  # rtsp | srt
    base_url: str  # rtsp://media:8554  |  srt://media:8890
    username: str | None  # device_uuid
    password: str | None  # device key (or a publish token)


def create_publisher(endpoint: PublishEndpoint, path: str, settings: EncoderSettings,
                     encoder_factory: EncoderFactory) -> StreamPublisher:
    if endpoint.protocol == "srt":
        return SRTPublisher(endpoint.base_url, path, endpoint.username, endpoint.password, settings, encoder_factory)
    if endpoint.protocol == "rtsp":
        return RTSPPublisher(endpoint.base_url, path, endpoint.username, endpoint.password, settings, encoder_factory)
    raise ValueError(f"unsupported stream protocol '{endpoint.protocol}' (webrtc/WHIP: future)")
