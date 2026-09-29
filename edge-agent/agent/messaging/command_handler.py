"""Handles server/{device}/command and server/{device}/config."""

from __future__ import annotations

import logging
from collections.abc import Callable

from pydantic import ValidationError

from aivms_shared.payloads import Command, CommandType, ConfigChanged

logger = logging.getLogger(__name__)

CommandCallback = Callable[[Command], None]


class CommandHandler:
    def __init__(self) -> None:
        self._handlers: dict[CommandType, CommandCallback] = {}
        self._on_config_changed: Callable[[ConfigChanged], None] | None = None

    def register(self, command: CommandType, callback: CommandCallback) -> None:
        self._handlers[command] = callback

    def on_config_changed(self, callback: Callable[[ConfigChanged], None]) -> None:
        self._on_config_changed = callback

    def handle_command(self, topic: str, payload: bytes) -> None:
        try:
            cmd = Command.model_validate_json(payload)
        except ValidationError as exc:
            logger.warning("invalid command on %s: %s", topic, exc.errors()[:2])
            return
        handler = self._handlers.get(cmd.command)
        if handler is None:
            logger.warning("no handler for command %s", cmd.command)
            return
        logger.info("executing command %s (%s)", cmd.command, cmd.command_id)
        handler(cmd)

    def handle_config(self, topic: str, payload: bytes) -> None:
        if not payload:
            return
        try:
            msg = ConfigChanged.model_validate_json(payload)
        except ValidationError:
            logger.warning("invalid config notification on %s", topic)
            return
        if self._on_config_changed:
            self._on_config_changed(msg)
