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
