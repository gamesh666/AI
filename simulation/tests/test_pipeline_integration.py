"""Integration: production pipeline + simulation plugin (synthetic camera, mock detector); no network."""

import time

import agent.camera.pipeline as pipeline_mod
import numpy as np
from agent.camera.manager import CameraManager
from agent.camera.pipeline import CameraPipeline, PipelineContext
from agent.config.settings import AgentSettings
from agent.streaming.factory import PublishEndpoint
from aivms_shared.payloads import AiStatus, RtspStatus, StreamStatus


class FakeMQTT:
    def __init__(self):
        self.events, self.statuses = [], []

    def detection(self, event):
        self.events.append(event)

    def camera_status(self, status):
        self.statuses.append(status)


class RecordingPublisher:
    """StreamPublisher double; can simulate a media server outage."""

    def __init__(self):
        self.frames: list[np.ndarray] = []
        self.status = StreamStatus.CONNECTING
        self.last_error = None
        self.down = False

    def publish(self, frame):
        if self.down:
            self.status, self.last_error = StreamStatus.ERROR, "media server unavailable"
            return False
        self.frames.append(frame)
        self.status = StreamStatus.STREAMING
        return True

    def stop(self):
        self.status = StreamStatus.OFFLINE


def _ctx(mqtt):
    s = AgentSettings(device_uuid="EDGE001", detector="mock", tracker="iou", min_confidence=0.5,
                      snapshot_enabled=False)
    return PipelineContext(settings=s, device_id="EDGE001", publisher=mqtt, uploader=None,
                           endpoint=PublishEndpoint("rtsp", "rtsp://127.0.0.1:1", "EDGE001", "k"))


def test_pipeline_streams_annotated_video_and_emits_events(monkeypatch, camera_config):
    publishers = []
    monkeypatch.setattr(pipeline_mod, "create_publisher",
                        lambda *a, **k: publishers.append(RecordingPublisher()) or publishers[-1])
    mqtt = FakeMQTT()
    p = CameraPipeline(camera_config("CAM001"), _ctx(mqtt))
    p.start()
    try:
        time.sleep(2.0)
        # media server goes down: streaming fails, AI keeps running
        publishers[0].down = True
        events_before = len(mqtt.events)
        time.sleep(1.5)
        st = p.status()
    finally:
        p.stop()

    frames = publishers[0].frames
    assert 10 <= len(frames) <= 25, len(frames)  # ~10 fps for ~2 s
    assert frames[0].shape == (180, 320, 3)
    assert st.rtsp_status == RtspStatus.ONLINE and st.ai_status == AiStatus.RUNNING
    assert st.stream_status == StreamStatus.ERROR and "media server unavailable" in st.error
    assert st.inference_fps > 2 and st.input_fps > 15
    assert mqtt.events and all(d.track_id for e in mqtt.events for d in e.detections)
    assert mqtt.events[0].camera_id == "CAM001" and mqtt.events[0].frame.width == 320
    assert st.inference_fps > 0 and len(mqtt.events) >= events_before


def test_camera_failures_are_isolated(monkeypatch, camera_config):
    monkeypatch.setattr(pipeline_mod, "create_publisher", lambda *a, **k: RecordingPublisher())

    def factory(camera, ctx):
        if camera.camera_id == "CAM002":
            raise RuntimeError("bad camera config")
        return CameraPipeline(camera, ctx)

    mgr = CameraManager(_ctx(FakeMQTT()), factory=factory)
    cams = [camera_config("CAM001"), camera_config("CAM002"),
            camera_config("CAM003", rtsp_url="rtsp://127.0.0.1:1/unreachable")]
    mgr.apply(cams)
    try:
        time.sleep(1.5)
        statuses = {s.camera_id: s for s in mgr.statuses()}
    finally:
        mgr.stop_all()
    assert set(statuses) == {"CAM001", "CAM003"}
    assert statuses["CAM001"].rtsp_status == RtspStatus.ONLINE and statuses["CAM001"].output_fps > 0
    assert statuses["CAM003"].rtsp_status in (RtspStatus.OFFLINE, RtspStatus.CONNECTING)


def test_manager_restarts_only_changed_cameras(monkeypatch, camera_config):
    monkeypatch.setattr(pipeline_mod, "create_publisher", lambda *a, **k: RecordingPublisher())
    mgr = CameraManager(_ctx(FakeMQTT()))
    mgr.apply([camera_config("CAM001"), camera_config("CAM002")])
    try:
        first = dict(mgr._pipelines)
        mgr.apply([camera_config("CAM001"), camera_config("CAM002", name="Renamed")])
        assert mgr._pipelines["CAM001"] is first["CAM001"]
        assert mgr._pipelines["CAM002"] is not first["CAM002"]
        mgr.apply([camera_config("CAM001")])
        assert mgr.camera_ids() == ["CAM001"]
    finally:
        mgr.stop_all()
