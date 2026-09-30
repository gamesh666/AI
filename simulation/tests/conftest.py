"""Simulation tests run the PRODUCTION edge agent with the simulation plugin registered."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "edge-agent", ROOT / "simulation" / "python"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from agent.config.models import CameraConfig, VideoConfig  # noqa: E402

from aivms_sim.edge import plugin  # noqa: E402

plugin.register()


@pytest.fixture
def camera_config():
    def make(camera_id="CAM001", **kw) -> CameraConfig:
        base = dict(
            id=f"00000000-0000-0000-0000-000000000{camera_id[-3:]}",
            camera_id=camera_id,
            name=f"Camera {camera_id}",
            rtsp_url="mock://scene?seed=1&width=320&height=180&fps=25",
            stream_path=f"ai/site01/EDGE001/{camera_id}",
            original_stream_path=f"original/site01/EDGE001/{camera_id}",
            video=VideoConfig(stream_fps=10, inference_fps=5, width=320, height=180),
        )
        base.update(kw)
        return CameraConfig(**base)

    return make
