"""paho-mqtt wrapper: auto-reconnect, Last Will, re-subscribe on reconnect, offline queueing."""

from __future__ import annotations

import logging
import ssl
import threading
from collections.abc import Callable

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

logger = logging.getLogger(__name__)

MessageCallback = Callable[[str, bytes], None]


class EdgeMQTTClient:
    def __init__(
        self,
        client_id: str,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        tls: bool = False,
        keepalive: int = 30,
        max_queued: int = 5000,
    ) -> None:
        self._host, self._port, self._keepalive = host, port, keepalive
        self._client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv5,
        )
        if username:
            self._client.username_pw_set(username, password)
        if tls:
            self._client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        # QoS>0 messages published while offline are queued and flushed on reconnect
        self._client.max_queued_messages_set(max_queued)
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._subscriptions: dict[str, tuple[int, MessageCallback]] = {}
        self._connected = threading.Event()
        self._on_connected_hooks: list[Callable[[], None]] = []

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    def set_will(self, topic: str, payload: bytes, qos: int = 1, retain: bool = True) -> None:
        self._client.will_set(topic, payload, qos=qos, retain=retain)

    def on_connected(self, hook: Callable[[], None]) -> None:
        self._on_connected_hooks.append(hook)

    def subscribe(self, topic: str, callback: MessageCallback, qos: int = 1) -> None:
        self._subscriptions[topic] = (qos, callback)
        if self.connected:
            self._client.subscribe(topic, qos=qos)

    def publish(self, topic: str, payload: bytes, qos: int = 1, retain: bool = False) -> None:
        info = self._client.publish(topic, payload, qos=qos, retain=retain)
        if info.rc not in (mqtt.MQTT_ERR_SUCCESS, mqtt.MQTT_ERR_NO_CONN):
            logger.warning("publish to %s failed rc=%s", topic, info.rc)

    def start(self) -> None:
        self._client.connect_async(self._host, self._port, keepalive=self._keepalive)
        self._client.loop_start()

    def wait_connected(self, timeout: float | None = None) -> bool:
        return self._connected.wait(timeout)

    def stop(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()

    # ---- callbacks -----------------------------------------------------------

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            logger.error("MQTT connect refused: %s", reason_code)
            return
        logger.info("MQTT connected to %s:%s", self._host, self._port)
        for topic, (qos, _) in self._subscriptions.items():
            client.subscribe(topic, qos=qos)
        self._connected.set()
        for hook in self._on_connected_hooks:
            try:
                hook()
            except Exception:
                logger.exception("on_connected hook failed")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties) -> None:
        self._connected.clear()
        logger.warning("MQTT disconnected (%s); paho will reconnect", reason_code)

    def _on_message(self, client, userdata, message) -> None:
        entry = self._subscriptions.get(message.topic)
        if entry is None:
            return
        try:
            entry[1](message.topic, message.payload)
        except Exception:
            logger.exception("message callback failed for %s", message.topic)
