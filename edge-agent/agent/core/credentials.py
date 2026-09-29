"""Persists the device API key obtained at registration (file mode 0600)."""

from __future__ import annotations

import json
import os
from pathlib import Path


class CredentialStore:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "credentials.json"

    def load(self, device_uuid: str) -> str | None:
        if not self.path.is_file():
            return None
        try:
            data = json.loads(self.path.read_text())
        except ValueError:
            return None
        return data.get("api_key") if data.get("device_uuid") == device_uuid else None

    def save(self, device_uuid: str, api_key: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump({"device_uuid": device_uuid, "api_key": api_key}, fh)
        os.replace(tmp, self.path)

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)
