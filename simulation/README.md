# Development / Simulation Mode

Run and demonstrate the complete platform **without IP cameras, NVIDIA GPUs or edge hardware**.

```bash
./scripts/generate-secrets.sh > .env          # once (also creates the SIM_* credentials)
docker compose --profile demo up -d
# open http://localhost:3000  — user: admin, password: INITIAL_ADMIN_PASSWORD in .env
```

Within about a minute the frontend shows 2 sites, 2 edge devices, 4 cameras with live AI-annotated
video, detection events, device telemetry and per-camera health.

---

## What runs

| Service | Role | Replaced in production by |
|---------|------|---------------------------|
| `fake-camera01..04` | FFmpeg → H.264 RTSP (`test/camera01..04`, default 1920x1080 @ 30 fps). Test pattern or looped mp4 | IP cameras |
| `sim-rtsp` | The site's "camera LAN": RTSP server that hosts the fake cameras (camera credentials required) | the cameras' own RTSP servers |
| `edge01`, `edge02` | **The production edge agent** + the simulation plugin (`EDGE001`, `EDGE002`) | the same agent on edge hardware |
| `demo-seed` | One-shot: creates sites / devices / cameras via the **public REST API** | an operator using the UI / API |

Core services (frontend, backend, postgres, redis, mosquitto, mediamtx, minio) are the unchanged
production services.

```
            camera-lan (internal network)                 default network (central platform)
 ┌──────────────────────────────────────────┐     ┌────────────────────────────────────────────┐
 │ fake-camera01 ─┐                          │     │                                            │
 │ fake-camera02 ─┼─► sim-rtsp :8554 ◄─ RTSP ─┼─ edge01 (EDGE001: CAM001, CAM002) ─┐            │
 │ fake-camera03 ─┤   test/camera01..04       │     │                              ├─► MediaMTX  │ ai/<site>/<edge>/<cam>
 │ fake-camera04 ─┘                    ◄─ RTSP ─┼─ edge02 (EDGE002: CAM003, CAM004) ─┘   Mosquitto │ metadata / status
 └──────────────────────────────────────────┘     │                                   Backend   │
                                                   └────────────────────────────────────────────┘
```

The central platform is **not** attached to `camera-lan`: exactly as in production it cannot reach a
camera; the edges pull from the cameras and push everything out.

### Demo topology

| Site | Edge device | Camera | Fake stream (camera LAN) | Annotated stream (central) |
|------|-------------|--------|--------------------------|----------------------------|
| site01 Demo Site A | EDGE001 | CAM001 Main Entrance | `test/camera01` | `ai/site01/EDGE001/CAM001` |
| | | CAM002 Parking Lot | `test/camera02` | `ai/site01/EDGE001/CAM002` |
| site02 Demo Site B | EDGE002 | CAM003 Construction Yard | `test/camera03` | `ai/site02/EDGE002/CAM003` |
| | | CAM004 Loading Dock | `test/camera04` | `ai/site02/EDGE002/CAM004` |

Defined in `python/aivms_sim/seed/topology.py`.

### Data flow (identical to production)

```
fake-camera ─RTSP─► edge (capture → MockDetector|YOLO → tracker → overlay → H.264) ─RTSP push─► MediaMTX ─WebRTC/HLS─► browser
                         └─ detections ─MQTT─► backend ─► PostgreSQL ─► Redis ─► WebSocket ─► browser
```

---

## Simulation components

All simulation code lives in `simulation/`; production code never imports it
(`edge-agent/tests/test_no_simulation_dependency.py` enforces this).

| Component | File | Plugged in through |
|-----------|------|--------------------|
| Fake RTSP camera | `fake-camera/publish.sh` | a normal `rtsp://` camera URL |
| MockDetector (person / car / truck / excavator, new object every few seconds) | `python/aivms_sim/edge/mock_detector.py` | detector registry, `DETECTOR_TYPE=mock` |
| `file://` (looped mp4) and `mock://` (generated frames) sources | `python/aivms_sim/edge/sources.py` | camera-source registry |
| Simulated GPU telemetry | `python/aivms_sim/edge/metrics.py` | metrics registry, `EDGE_METRICS_PROVIDER=simulated` |
| Plugin entry point | `python/aivms_sim/edge/plugin.py` | `EDGE_PLUGINS=aivms_sim.edge.plugin` |
| Demo data seeder | `python/aivms_sim/seed/` | public REST API |

MockDetector returns the very same `Detection` objects as `YoloDetector`
(`class_id`, `class_name`, `confidence`, `bbox{x1,y1,x2,y2}`), so tracking, overlay, events, MQTT, the
database and the frontend cannot tell them apart.

---

## Switching to real hardware

Nothing in the backend, frontend, MQTT contracts, database or streaming architecture changes.

| Simulation | Real | How |
|------------|------|-----|
| fake camera | IP camera | edit the camera in the UI: `rtsp://<camera-ip>:554/...` + its credentials |
| MockDetector | YoloDetector | `DETECTOR_TYPE=yolo` + `pip install -r requirements-yolo.txt` + model path on the AI model |
| simulated edge | edge hardware | run `edge-agent/Dockerfile` (production image) on the device; drop `EDGE_PLUGINS` and `EDGE_METRICS_PROVIDER` |

`DETECTOR_TYPE=yolo` with `EDGE_DETECTOR_FALLBACK=mock` (the demo default) uses YOLO when a model and
Ultralytics are available and the mock otherwise — handy for gradually bringing up real inference.

---

## Configuration

`.env` (see `.env.example`, section *Simulation*):

| Variable | Default | Meaning |
|----------|---------|---------|
| `SIM_CAMERA_USERNAME` / `SIM_CAMERA_PASSWORD` | `admin` / generated | credentials of the simulated cameras (stored encrypted in the platform) |
| `SIM_CAMERA_PUBLISH_PASSWORD` | generated | fake cameras → camera LAN |
| `SIM_CAMERA_WIDTH` / `HEIGHT` / `FPS` | 1920 / 1080 / 30 | fake camera output |
| `FAKE_CAMERA0N_SOURCE` / `FAKE_CAMERA0N_VIDEO` | `testsrc` / – | `file` + `/media/<name>.mp4` to loop a video from `simulation/media/` |
| `DEMO_DETECTOR_TYPE` | `mock` | `yolo` to try real inference (falls back to mock) |
| `DEMO_STREAM_RESOLUTION` / `DEMO_STREAM_FPS` / `DEMO_INFERENCE_FPS` | 1280x720 / 25 / 5 | per-camera settings the seeder applies |

Resource usage: four 1080p30 encoders + four decoders + four 720p25 encoders keep a 4-core machine
busy. On small machines set `SIM_CAMERA_WIDTH=1280`, `SIM_CAMERA_HEIGHT=720`, `SIM_CAMERA_FPS=15`.

## Tests

```bash
pip install -r edge-agent/requirements-dev.txt -e shared/python -e simulation/python
cd simulation && pytest        # production pipeline + simulation plugin (no Docker needed)
```
