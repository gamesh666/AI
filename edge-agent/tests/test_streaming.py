import numpy as np

from agent.core.backoff import Backoff
from agent.streaming.factory import PublishEndpoint, create_publisher
from agent.streaming.passthrough import build_passthrough_command
from agent.streaming.rtsp_publisher import RTSPPublisher, build_rtsp_url
from agent.streaming.srt_publisher import SRTPublisher, build_srt_url
from agent.video.encoder import EncoderError, EncoderSettings, FFmpegEncoder, codec_args, parse_bitrate
from aivms_shared.payloads import StreamStatus


class FakeEncoder:
    """Fails `fail_writes` times, then accepts frames."""

    instances: list = []

    def __init__(self, settings, fail_start=False, fail_writes=0):
        self.settings, self.fail_start, self.fail_writes = settings, fail_start, fail_writes
        self.frames, self._alive = 0, False
        FakeEncoder.instances.append(self)

    def start(self, url, fmt, extra=None):
        if self.fail_start:
            raise EncoderError("connection refused")
        self.url, self.fmt, self.extra, self._alive = url, fmt, extra, True

    def write(self, image):
        if self.fail_writes:
            self.fail_writes -= 1
            self._alive = False
            raise EncoderError("broken pipe")
        self.frames += 1

    def close(self):
        self._alive = False

    @property
    def alive(self):
        return self._alive


FRAME = np.zeros((180, 320, 3), dtype=np.uint8)
SETTINGS = EncoderSettings(width=0, height=0, fps=25, bitrate="2M", gop_size=50, encoder="libx264")


def test_urls_carry_credentials_and_path():
    assert build_rtsp_url("rtsp://media:8554", "ai/site01/edge01/cam01", "edge01", "k/y") == \
        "rtsp://edge01:k%2Fy@media:8554/ai/site01/edge01/cam01"
    srt = build_srt_url("srt://media:8890", "ai/site01/edge01/cam01", "edge01", "key")
    assert srt.startswith("srt://media:8890?streamid=publish:ai/site01/edge01/cam01:edge01:key&pkt_size=1316")


def test_libx264_args_are_webrtc_friendly():
    args = codec_args("libx264", EncoderSettings(1920, 1080, 25, bitrate="4M", gop_size=50))
    assert args[args.index("-c:v") + 1] == "libx264"
    assert args[args.index("-bf") + 1] == "0" and args[args.index("-g") + 1] == "50"
    assert args[args.index("-b:v") + 1] == "4000000"
    assert parse_bitrate("800k") == 800_000


def test_forced_nvenc_and_command():
    enc = FFmpegEncoder(EncoderSettings(640, 360, 25, encoder="h264_nvenc"))
    cmd = enc.build_command("rtsp://m/ai/x", "rtsp", ["-rtsp_transport", "tcp"])
    assert cmd[cmd.index("-c:v") + 1] == "h264_nvenc"
    assert cmd[cmd.index("-s") + 1] == "640x360" and cmd[-3:] == ["-f", "rtsp", "rtsp://m/ai/x"]


def test_publisher_reconnects_with_backoff_without_blocking():
    now = [0.0]
    attempts = []

    def factory(settings):
        attempts.append(settings)
        return FakeEncoder(settings, fail_start=len(attempts) <= 2)

    pub = RTSPPublisher("rtsp://media:8554", "ai/s/e/c", "edge01", "key", SETTINGS, factory,
                        backoff=Backoff(clock=lambda: now[0]), settle_seconds=0, clock=lambda: now[0])
    assert not pub.publish(FRAME) and pub.status == StreamStatus.ERROR  # attempt 1 fails
    assert not pub.publish(FRAME) and len(attempts) == 1  # waiting: frame dropped, no new attempt
    now[0] = 1.1
    assert not pub.publish(FRAME) and len(attempts) == 2  # attempt 2 fails (next delay 2 s)
    now[0] = 2.5
    assert not pub.publish(FRAME) and len(attempts) == 2
    now[0] = 3.2
    assert pub.publish(FRAME) and pub.status == StreamStatus.STREAMING
    assert (attempts[-1].width, attempts[-1].height) == (320, 180)
    enc = FakeEncoder.instances[-1]
    assert enc.fmt == "rtsp" and enc.extra == ["-rtsp_transport", "tcp"]


def test_publisher_recovers_after_broken_pipe_and_resize():
    encoders = []
    pub = RTSPPublisher("rtsp://m:8554", "ai/s/e/c", None, None, SETTINGS,
                        lambda s: encoders.append(FakeEncoder(s, fail_writes=1 if not encoders else 0)) or encoders[-1],
                        backoff=Backoff(schedule=(0,)), settle_seconds=0)
    assert not pub.publish(FRAME)  # write fails -> error
    assert pub.publish(FRAME) and len(encoders) == 2
    assert pub.publish(np.zeros((360, 640, 3), dtype=np.uint8)) and len(encoders) == 3  # new size -> new encoder
    pub.stop()
    assert pub.status == StreamStatus.OFFLINE


def test_encoder_dying_on_its_own_backs_off_and_is_not_reported_as_streaming():
    """Regression: ffmpeg accepts the first frame, then exits because the media server is down."""
    now = [0.0]
    encoders = []

    def factory(settings):
        encoders.append(FakeEncoder(settings))
        return encoders[-1]

    pub = RTSPPublisher("rtsp://m:8554", "ai/s/e/c", None, None, SETTINGS, factory,
                        backoff=Backoff(clock=lambda: now[0]), settle_seconds=2, clock=lambda: now[0])
    assert pub.publish(FRAME) and pub.status == StreamStatus.CONNECTING  # accepted, not yet confirmed
    encoders[-1]._alive = False  # connection refused -> process exits
    assert not pub.publish(FRAME) and pub.status == StreamStatus.ERROR
    assert not pub.publish(FRAME) and len(encoders) == 1  # backing off (1 s), no reconnect storm
    now[0] = 1.5
    assert pub.publish(FRAME) and len(encoders) == 2 and pub.status == StreamStatus.CONNECTING
    now[0] = 4.0
    assert pub.publish(FRAME) and pub.status == StreamStatus.STREAMING  # stayed up > settle time


def test_publisher_factory_and_srt_format():
    ep = PublishEndpoint("srt", "srt://media:8890", "edge01", "key")
    pub = create_publisher(ep, "ai/s/e/c", SETTINGS, lambda s: FakeEncoder(s))
    assert isinstance(pub, SRTPublisher) and pub.output_format == "mpegts"
    assert "key" not in pub.display_url


def test_passthrough_copies_without_reencoding():
    ep = PublishEndpoint("rtsp", "rtsp://media:8554", "edge01", "key")
    cmd = build_passthrough_command("ffmpeg", "rtsp://192.168.1.101/s", ep, "original/site01/edge01/cam01")
    assert cmd[cmd.index("-c") + 1] == "copy"
    assert cmd[-1] == "rtsp://edge01:key@media:8554/original/site01/edge01/cam01"
