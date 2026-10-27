# Reference edge (HTTP)

Minimal program showing how an edge (e.g. a REACH AI BOX) plugs into the platform:
announce cameras, report health, push annotated H.264 video, and send free-form recognition logs.

Protocol: [`docs/edge-integration.md`](../../docs/edge-integration.md) (Chinese).

```bash
# standard library only (plus an ffmpeg binary on PATH). First start registers with the owner's provisioning
# token and keeps the device ID + key in edge-identity.json; later starts reuse it.
EDGE_API_URL=http://<platform>:8000/api/v1 EDGE_PROVISIONING_TOKEN=aivms_pt_... EDGE_MAC=02:00:00:00:00:01 \
EDGE_CAMERAS="cam01:Front door,cam02:Back office" \
python generic_edge.py
```

Replace `fake_recognition()` with your AI and the FFmpeg test pattern with your rendered frames.
