"""Edge agent lifecycle.

    register (provisioning token -> device key, cached)
      -> fetch config (REST)
      -> MQTT connect (LWT = offline status)
      -> start camera workers
      -> heartbeat every 10s, status on change / every 30s
      -> react to server/{id}/command and server/{id}/config
"""

from __future__ import annotations

import logging
import threading

from agent.api_client.client import ApiError, BackendClient
from agent.api_client.models import DeviceConfig
from agent.camera.manager import CameraManager
from agent.config import AgentSettings
from agent.core.credentials import CredentialStore
from agent.messaging.command_handler import CommandHandler
from agent.messaging.mqtt_client import EdgeMQTTClient
from agent.messaging.publisher import EdgePublisher
from agent.pipeline.camera_pipeline import PipelineDeps
from agent.storage.snapshot_uploader import SnapshotUploader
from agent.telemetry.heartbeat import HeartbeatReporter
from agent.telemetry.system_metrics import SystemMetrics
from aivms_shared import topics
from aivms_shared.payloads import Command, CommandType, ConfigChanged, DeviceState, DeviceStatus

logger = logging.getLogger(__name__)


class EdgeAgent:
    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings
        self.api = BackendClient(settings.api_url, settings.api_timeout_seconds)
        self.credentials = CredentialStore(settings.data_dir)
        self.metrics = SystemMetrics()
        self.commands = CommandHandler()
        self.config: DeviceConfig | None = None
        self._stop = threading.Event()
        self._reload = threading.Event()
        self._last_status: list | None = None

        self.mqtt: EdgeMQTTClient | None = None
        self.publisher: EdgePublisher | None = None
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
                delay = min(delay * 2, 60)

    # ---- runtime ---------------------------------------------------------------

    def _relay_base(self) -> str | None:
        if self.settings.rtsp_publish_url:
            return self.settings.rtsp_publish_url
        return self.config.streaming.rtsp_publish_url if self.config else None

    def _setup_mqtt(self) -> None:
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
        self.publisher = EdgePublisher(self.mqtt, s.device_uuid)
        self.publisher.configure_last_will()
        self.mqtt.subscribe(topics.command(s.device_uuid), self.commands.handle_command)
        self.mqtt.subscribe(topics.config(s.device_uuid), self.commands.handle_config)
        self.mqtt.on_connected(lambda: self._publish_status(force=True))

        self.commands.register(CommandType.RELOAD_CONFIG, lambda _: self._reload.set())
        self.commands.register(CommandType.RESTART_CAMERA, self._cmd_restart_camera)
        self.commands.register(CommandType.PING, lambda _: self._publish_status(force=True))
        self.commands.on_config_changed(self._on_config_changed)

    def _cmd_restart_camera(self, cmd: Command) -> None:
        cam_id = str(cmd.params.get("camera_id", ""))
        if self.cameras and not self.cameras.restart(cam_id, self._relay_base()):
            logger.warning("restart_camera: unknown camera %s", cam_id)

    def _on_config_changed(self, msg: ConfigChanged) -> None:
        logger.info("config change notified (%s)", msg.reason)
        self._reload.set()

    def _apply_config(self) -> None:
        assert self.cameras is not None and self.config is not None
        self.cameras.apply(self.config.cameras, self._relay_base())
        if self.heartbeat:
            self.heartbeat.interval = self.config.heartbeat_interval_seconds or self.settings.heartbeat_interval_seconds
        self._publish_status(force=True)

    def _publish_status(self, force: bool = False) -> None:
        if not self.publisher or not self.cameras:
            return
        cams = self.cameras.statuses()
        snapshot = [(c.camera_id, c.state) for c in cams]
        if not force and snapshot == self._last_status:
            return
        self._last_status = snapshot
        self.publisher.status(DeviceStatus(device_uuid=self.settings.device_uuid, state=DeviceState.ONLINE,
                                           cameras=cams))

    def run(self) -> None:
        s = self.settings
        logger.info("edge agent starting (device=%s detector=%s)", s.device_uuid, s.detector)
        self._bootstrap()
        if self._stop.is_set():
            return
        self._setup_mqtt()
        assert self.mqtt is not None and self.publisher is not None

        uploader = SnapshotUploader(self.api, s.snapshot_jpeg_quality) if s.snapshot_enabled else None
        self.cameras = CameraManager(PipelineDeps(s, self.publisher, uploader, self.device_key))
        self.heartbeat = HeartbeatReporter(s.device_uuid, self.publisher, self.metrics, s.heartbeat_interval_seconds)

        self.mqtt.start()
        self.heartbeat.start()
        self._apply_config()

        ticks = 0.0
        while not self._stop.is_set():
            if self._reload.wait(timeout=5):
                self._reload.clear()
                self._reload_config()
            ticks += 5
            self._publish_status(force=ticks % s.status_interval_seconds < 5)
            if ticks % s.config_poll_interval_seconds < 5:
                self._reload_config()  # safety net if a config notification was missed

    def _reload_config(self) -> None:
        try:
            new = self._fetch_config()
        except Exception as exc:
            logger.error("config reload failed: %s", exc)
            return
        self.config = new
        self._apply_config()

    def stop(self) -> None:
        logger.info("edge agent stopping")
        self._stop.set()
        if self.heartbeat:
            self.heartbeat.stop()
        if self.cameras:
            self.cameras.stop_all()
        if self.publisher and self.mqtt and self.mqtt.connected:
            self.publisher.status(DeviceStatus(device_uuid=self.settings.device_uuid, state=DeviceState.OFFLINE))
        if self.mqtt:
            self.mqtt.stop()
        self.api.close()
