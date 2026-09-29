import pytest

from agent.config.models import CameraConfig, VideoConfig


@pytest.fixture
def camera_config():
    def make(camera_id="cam01", **kw) -> CameraConfig:
        base = dict(
            id=f"00000000-0000-0000-0000-0000000000{camera_id[-2:]}",
            camera_id=camera_id,
            name=f"Camera {camera_id}",
            rtsp_url="mock://scene?seed=1&width=320&height=180&fps=25",
            stream_path=f"ai/site01/edge01/{camera_id}",
            original_stream_path=f"original/site01/edge01/{camera_id}",
            video=VideoConfig(stream_fps=10, inference_fps=5, width=320, height=180),
        )
        base.update(kw)
        return CameraConfig(**base)

    return make
