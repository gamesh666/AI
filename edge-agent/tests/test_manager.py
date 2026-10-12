from agent.camera.manager import CameraManager


class _FakePipeline:
    def __init__(self, camera, ctx) -> None:
        self.camera = camera
        self.started = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False


def test_cameras_without_source_are_left_to_the_edge(camera_config):
    manager = CameraManager(ctx=None, factory=_FakePipeline)  # type: ignore[arg-type]
    manager.apply([camera_config("cam01"), camera_config("cam02", rtsp_url=None)])
    assert set(manager._pipelines) == {"cam01"}


def test_heartbeat_carries_reported_models():
    from agent.telemetry.heartbeat import HeartbeatReporter
    from agent.telemetry.system_metrics import GPUStats
    from aivms_shared.payloads import ReportedModel

    class Metrics:
        cpu_usage = memory_usage = staticmethod(lambda: 1.0)
        cpu_temperature = staticmethod(lambda: None)
        hostname = primary_ip = staticmethod(lambda: "h")

        @staticmethod
        def gpu():
            return GPUStats()

    models = [ReportedModel(name="yolo11n", version="1", cameras=["cam01"])]
    hb = HeartbeatReporter("edge01", publisher=None, metrics=Metrics(), interval=10, models=lambda: models).build()
    assert hb.models == models
    assert HeartbeatReporter("edge01", None, Metrics(), 10).build().models is None
