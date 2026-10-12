# Reference third-party edge

Minimal program showing how **any** edge (not using this repo's edge-agent) plugs into the platform:
announce cameras, report health, push annotated H.264 video, and send free-form recognition logs.

Protocol: [`docs/edge-integration.md`](../../docs/edge-integration.md) (Chinese).

```bash
# standard library only (plus an ffmpeg binary on PATH); everything goes over HTTP with the device key
EDGE_API_URL=http://<platform>:8000/api/v1 EDGE_DEVICE_ID=REACH01 EDGE_DEVICE_KEY=<key from the UI> \
EDGE_CAMERAS="cam01:Front door,cam02:Back office" \
python generic_edge.py

# legacy: heartbeat / logs over the shared MQTT account instead
pip install "paho-mqtt>=2"
EDGE_TELEMETRY=mqtt EDGE_MQTT_USERNAME=<MQTT_EDGE_USERNAME> EDGE_MQTT_PASSWORD=<MQTT_EDGE_PASSWORD> ... python generic_edge.py
```

Replace `fake_recognition()` with your AI and the FFmpeg test pattern with your rendered frames.
