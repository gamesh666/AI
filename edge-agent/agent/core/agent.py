"""Edge agent lifecycle.

    register (provisioning token -> device key, cached)
      -> fetch config (REST, HTTPS)
      -> telemetry: MQTT (LWT = offline) or HTTPS with the device key   outgoing
      -> CameraManager: one CameraPipeline per camera           camera RTSP in, annotated H.264 out (push)
      -> heartbeat every 10 s, per-camera health every 10 s + on state change
      -> react to commands / config changes (MQTT server/{id}/..., or the HTTP heartbeat answer)
"""

from __future__ import annotations

import json
import logging
import threading
import time

from agent.api_client.client import ApiError, BackendClient
from agent.camera.manager import CameraManager
from agent.camera.pipeline import PipelineContext
from agent.config.models import DeviceConfig
from agent.config.settings import AgentSettings
from agent.core.credentials import CredentialStore
from agent.messaging.command_handler import CommandHandler
from agent.messaging.http_publisher import HttpPublisher
from agent.messaging.mqtt import EdgeMQTTClient
from agent.messaging.publisher import EdgePublisher, SwitchablePublisher
from agent.storage.snapshot_uploader import SnapshotUploader
from agent.streaming.factory import PublishEndpoint
from agent.telemetry.heartbeat import HeartbeatReporter
from agent.telemetry.system_metrics import create_metrics
from aivms_shared import topics
from aivms_shared.payloads import Command, CommandType, ConfigChanged, DeviceState, DeviceStatus, ReportedModel

logger = logging.getLogger(__name__)

LOOP_SECONDS = 2.0


class EdgeAgent:
    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings
        self.api = BackendClient(settings.api_url, settings.api_timeout_seconds)
        self.credentials = CredentialStore(settings.data_dir)
        self.metrics = create_metrics(settings.metrics_provider)
        self.commands = CommandHandler()
        self.config: DeviceConfig | None = None
        self._stop = threading.Event()
        self._reload = threading.Event()
        self._last_states: dict[str, tuple] = {}
        self._last_status_report = 0.0

        self.mqtt: EdgeMQTTClient | None = None
        self.http: HttpPublisher | None = None
        self.publisher: SwitchablePublisher | None = None
        self.transport: str | None = None  # "mqtt" | "http"
        self._config_version: int | None = None
        self.cameras: CameraManager | None = None
        self.heartbeat: HeartbeatReporter | None = None
        self.device_key: str = ""

    # ---- bootstrap -------------------------------------------------------------

    def _obtain_device_key(self) -> str:
        s = self.settings
        if s.device_key:
            return s.device_key.get_secret_value()
        if cached := self.credentials.load(s.device_uuid):
            return cached
        if not s.provisioning_token:
            raise RuntimeError("no device key cached and EDGE_PROVISIONING_TOKEN not set")
        logger.info("registering device %s", s.device_uuid)
        gpu = self.metrics.gpu()
        key = self.api.register(
            s.provisioning_token.get_secret_value(),
            s.device_uuid,
            name=s.device_name,
            hostname=self.metrics.hostname(),
            ip_address=self.metrics.primary_ip(),
            gpu_name=gpu.name,
            gpu_memory=gpu.total_memory_mb,
        )
        self.credentials.save(s.device_uuid, key)
        return key

    def _fetch_config(self) -> DeviceConfig:
        try:
            return self.api.get_config()
        except ApiError as exc:
            if exc.status_code == 401 and self.settings.provisioning_token and not self.settings.device_key:
                logger.warning("device key rejected; re-registering")
                self.credentials.clear()
                self.device_key = self._obtain_device_key()
                self.api.set_device_key(self.device_key)
                return self.api.get_config()
            raise

    def _bootstrap(self) -> None:
        delay = 2.0
        while not self._stop.is_set():
            try:
                self.device_key = self._obtain_device_key()
                self.api.set_device_key(self.device_key)
                self.config = self._fetch_config()
                return
            except Exception as exc:
                logger.error("bootstrap failed (%s); retrying in %.0fs", exc, delay)
                self._stop.wait(delay)
                delay = min(delay * 2, 30)

    # ---- runtime ---------------------------------------------------------------

    def _endpoint(self) -> PublishEndpoint:
        s, cfg = self.settings, self.config
        assert cfg is not None
        protocol = s.stream_protocol or cfg.streaming.protocol
        if protocol == "srt":
            base = s.srt_publish_url or cfg.streaming.srt_publish_url
            if not base:
                raise RuntimeError("SRT selected but no srt_publish_url configured")
        else:
            base = s.rtsp_publish_url or cfg.streaming.rtsp_publish_url
        return PublishEndpoint(protocol=protocol, base_url=base, username=s.device_uuid, password=self.device_key)

    def _wanted_transport(self) -> str:
        s, cfg = self.settings, self.config
        assert cfg is not None
        if s.telemetry != "auto":
            return s.telemetry
        return "mqtt" if cfg.telemetry.mqtt_enabled and s.mqtt_username else "http"

    def _register_commands(self) -> None:
        self.commands.register(CommandType.RELOAD_CONFIG, lambda _: self._reload.set())
        self.commands.register(CommandType.RESTART_CAMERA, self._cmd_restart_camera)
        self.commands.register(CommandType.PING, lambda _: self._report_cameras(force=True))
        self.commands.on_config_changed(self._on_config_changed)

    def _setup_mqtt(self) -> EdgePublisher:
        s, cfg = self.settings, self.config
        assert cfg is not None
        self.mqtt = EdgeMQTTClient(
            client_id=f"edge-{s.device_uuid}",
            host=s.mqtt_host or cfg.mqtt.host,
            port=s.mqtt_port or cfg.mqtt.port,
            username=s.mqtt_username,
            password=s.mqtt_password.get_secret_value() if s.mqtt_password else None,
            tls=s.mqtt_tls or cfg.mqtt.tls,
            keepalive=s.mqtt_keepalive,
            max_queued=s.mqtt_max_queued_messages,
        )
        publisher = EdgePublisher(self.mqtt, s.device_uuid)
        publisher.configure_last_will()
        self.mqtt.subscribe(topics.command(s.device_uuid), self.commands.handle_command)
        self.mqtt.subscribe(topics.config(s.device_uuid), self.commands.handle_config)
        self.mqtt.on_connected(self._on_mqtt_connected)
        return publisher

    def _start_transport(self, transport: str) -> None:
        """Connects MQTT or starts the HTTP sender and points the shared publisher at it."""
        if transport == "mqtt":
            target = self._setup_mqtt()
        else:
            self.http = HttpPublisher(self.api, self._on_heartbeat_ack, self.settings.mqtt_max_queued_messages)
            target = self.http
        if self.publisher is None:
            self.publisher = SwitchablePublisher(target)
        else:
            self.publisher.target = target
        self.transport = transport
        logger.info("telemetry over %s", transport.upper())
        if transport == "mqtt":
            assert self.mqtt is not None
            self.mqtt.start()
        else:
            assert self.http is not None
            self.http.start()
            self.publisher.status(DeviceStatus(device_uuid=self.settings.device_uuid, state=DeviceState.ONLINE))

    def _switch_to_http(self) -> None:
        """The platform switched the shared MQTT account off: carry on over HTTP."""
        logger.warning("platform no longer offers MQTT; switching telemetry to HTTP")
        old = self.mqtt
        self._start_transport("http")
        self.mqtt = None
        if old:
            old.stop()
        self._report_cameras(force=True)

    def _on_heartbeat_ack(self, ack: dict) -> None:
        """HTTP only: commands and config changes ride back on the heartbeat answer."""
        for cmd in ack.get("commands") or []:
            self.commands.handle_command("http:heartbeat", json.dumps(cmd).encode())
        version = ack.get("config_version")
        if version is not None:
            if self._config_version is not None and version != self._config_version:
                logger.info("config version %s -> %s", self._config_version, version)
                self._reload.set()
            self._config_version = version

    def _on_mqtt_connected(self) -> None:
        assert self.publisher is not None
        self.publisher.status(DeviceStatus(device_uuid=self.settings.device_uuid, state=DeviceState.ONLINE))
        self._report_cameras(force=True)

    def _cmd_restart_camera(self, cmd: Command) -> None:
        cam_id = str(cmd.params.get("camera_id", ""))
        if self.cameras and not self.cameras.restart(cam_id):
            logger.warning("restart_camera: unknown camera %s", cam_id)

    def _on_config_changed(self, msg: ConfigChanged) -> None:
        logger.info("config change notified (%s)", msg.reason)
        self._reload.set()

    def _apply_config(self) -> None:
        assert self.cameras is not None and self.config is not None
        self.cameras.set_endpoint(self._endpoint())
        self.cameras.apply(self.config.cameras)
        if self.heartbeat:
            self.heartbeat.interval = self.config.heartbeat_interval_seconds or self.settings.heartbeat_interval_seconds
        self._report_cameras(force=True)

    def _reported_models(self) -> list[ReportedModel] | None:
        """Models assigned to running cameras, so the platform shows what this edge actually uses."""
        if self.config is None:
            return None
        by_model: dict[str, ReportedModel] = {}
        for cam in self.config.cameras:
            if not (cam.enabled and cam.ai_enabled and cam.ai_model and cam.rtsp_url):
                continue
            m = cam.ai_model
            entry = by_model.setdefault(m.id, ReportedModel(
                name=m.name, version=m.version, type=m.model_type, labels=m.labels[:1000],
                cameras=[],
            ))
            entry.cameras.append(cam.camera_id)
        return list(by_model.values())

    def _report_cameras(self, force: bool = False) -> None:
        """Per-camera health → edge/{device}/cameras/{camera}/status (periodic + on state change)."""
        if not self.publisher or not self.cameras or not self.publisher.ready:
            return
        periodic = time.monotonic() - self._last_status_report >= self.settings.camera_status_interval_seconds
        statuses = self.cameras.statuses()
        for status in statuses:
            key = (status.rtsp_status, status.ai_status, status.stream_status)
            if force or periodic or self._last_states.get(status.camera_id) != key:
                self._last_states[status.camera_id] = key
                self.publisher.camera_status(status)
        if force or periodic:
            self._last_status_report = time.monotonic()

    def run(self) -> None:
        s = self.settings
        logger.info("edge agent starting (device=%s detector=%s fallback=%s encoder=%s metrics=%s)", s.device_uuid,
                    s.detector, s.detector_fallback, s.video_encoder, s.metrics_provider)
        self._bootstrap()
        if self._stop.is_set():
            return
        self._register_commands()
        self._start_transport(self._wanted_transport())
        assert self.publisher is not None

        uploader = SnapshotUploader(self.api, s.snapshot_jpeg_quality) if s.snapshot_enabled else None
        ctx = PipelineContext(settings=s, device_id=s.device_uuid, publisher=self.publisher, uploader=uploader,
                              endpoint=self._endpoint())
        self.cameras = CameraManager(ctx)
        self.heartbeat = HeartbeatReporter(s.device_uuid, self.publisher, self.metrics, s.heartbeat_interval_seconds,
                                           models=self._reported_models)

        self.heartbeat.start()
        self._apply_config()

        last_poll = time.monotonic()
        while not self._stop.is_set():
            if self._reload.wait(timeout=LOOP_SECONDS):
                self._reload.clear()
                self._reload_config()
            self.cameras.supervise()
            self._report_cameras()
            if time.monotonic() - last_poll >= s.config_poll_interval_seconds:
                last_poll = time.monotonic()
                self._reload_config()  # safety net if a config notification was missed

    def _reload_config(self) -> None:
        try:
            new = self._fetch_config()
        except Exception as exc:
            logger.error("config reload failed: %s", exc)
            return
        self.config = new
        if self.transport == "mqtt" and self._wanted_transport() == "http":
            self._switch_to_http()
        self._apply_config()

    def stop(self) -> None:
        logger.info("edge agent stopping")
        self._stop.set()
        if self.heartbeat:
            self.heartbeat.stop()
        if self.cameras:
            self.cameras.stop_all()
        if self.publisher and self.publisher.ready:
            self.publisher.status(DeviceStatus(device_uuid=self.settings.device_uuid, state=DeviceState.OFFLINE))
        if self.mqtt:
            self.mqtt.stop()
        if self.http:
            self.http.stop()
        self.api.close()
