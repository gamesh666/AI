import time

from agent.api_client.client import ApiError
from agent.messaging.http_publisher import HttpPublisher
from agent.messaging.publisher import SwitchablePublisher
from aivms_shared.payloads import (
    AiStatus,
    CameraRuntimeStatus,
    DetectionEvent,
    Heartbeat,
    RtspStatus,
    StreamStatus,
)


class FakeApi:
    def __init__(self, fail_first: int = 0, status_code: int | None = None, answer=None):
        self.sent: list[str] = []
        self._fail = fail_first
        self._status = status_code
        self._answer = answer

    def post_telemetry(self, path, body):
        if self._fail:
            self._fail -= 1
            raise ApiError("down", self._status)
        self.sent.append(path)
        return self._answer


def wait_for(cond, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def hb():
    return Heartbeat(device_uuid="REACH01", cpu_usage=1, memory_usage=2, agent_version="t")


def test_payloads_go_to_the_matching_endpoints():
    api = FakeApi()
    pub = HttpPublisher(api)
    pub.start()
    pub.heartbeat(hb())
    pub.camera_status(CameraRuntimeStatus(camera_id="front", rtsp_status=RtspStatus.ONLINE,
                                          ai_status=AiStatus.RUNNING, stream_status=StreamStatus.STREAMING))
    pub.detection(DetectionEvent(device_id="REACH01", camera_id="front", model="m", detections=[]))
    assert wait_for(lambda: len(api.sent) == 3)
    assert api.sent == ["/edge/heartbeat", "/edge/cameras/front/status", "/edge/events"]
    pub.stop()


def test_heartbeat_answer_is_handed_back():
    acks = []
    api = FakeApi(answer={"config_version": 7, "commands": []})
    pub = HttpPublisher(api, acks.append)
    pub.start()
    pub.heartbeat(hb())
    assert wait_for(lambda: acks == [{"config_version": 7, "commands": []}])
    pub.stop()


def test_events_are_retried_while_the_platform_is_unreachable(monkeypatch):
    monkeypatch.setattr(HttpPublisher, "RETRY_DELAY_SECONDS", 0.01)
    api = FakeApi(fail_first=2)
    pub = HttpPublisher(api)
    pub.start()
    pub.detection(DetectionEvent(device_id="REACH01", camera_id="front", model="m", detections=[]))
    assert wait_for(lambda: api.sent == ["/edge/events"])
    pub.stop()


def test_refused_messages_are_not_retried(monkeypatch):
    monkeypatch.setattr(HttpPublisher, "RETRY_DELAY_SECONDS", 0.01)
    api = FakeApi(fail_first=1, status_code=422)
    pub = HttpPublisher(api)
    pub.start()
    pub.detection(DetectionEvent(device_id="REACH01", camera_id="front", model="m", detections=[]))
    pub.heartbeat(hb())
    assert wait_for(lambda: api.sent == ["/edge/heartbeat"])
    pub.stop()


def test_full_queue_drops_the_oldest():
    pub = HttpPublisher(FakeApi(), max_queued=2)  # not started: nothing is sent
    for _ in range(3):
        pub.heartbeat(hb())
    assert pub._queue.qsize() == 2


def test_switchable_publisher_follows_its_target():
    a, b = FakeApi(), FakeApi()
    pa, pb = HttpPublisher(a), HttpPublisher(b)
    sw = SwitchablePublisher(pa)
    sw.heartbeat(hb())
    sw.target = pb
    sw.heartbeat(hb())
    assert pa._queue.qsize() == 1 and pb._queue.qsize() == 1
