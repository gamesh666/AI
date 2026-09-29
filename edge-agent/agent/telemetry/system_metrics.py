"""Host metrics: CPU / memory / temperature via psutil, GPU via NVML (optional) or nvidia-smi."""

from __future__ import annotations

import logging
import shutil
import socket
import subprocess
from dataclasses import dataclass

import psutil

logger = logging.getLogger(__name__)


@dataclass
class GPUStats:
    name: str | None = None
    total_memory_mb: int | None = None
    usage: float | None = None
    memory_usage: float | None = None
    temperature: float | None = None


class SystemMetrics:
    def __init__(self) -> None:
        self._nvml = self._init_nvml()
        psutil.cpu_percent(interval=None)  # prime the counter

    @staticmethod
    def _init_nvml():
        try:
            import pynvml  # provided by nvidia-ml-py (optional)

            pynvml.nvmlInit()
            return pynvml
        except Exception:
            return None

    def cpu_usage(self) -> float:
        return float(psutil.cpu_percent(interval=None))

    def memory_usage(self) -> float:
        return float(psutil.virtual_memory().percent)

    def cpu_temperature(self) -> float | None:
        try:
            temps = psutil.sensors_temperatures()  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            return None
        for key in ("coretemp", "k10temp", "cpu_thermal", "soc_thermal", "acpitz"):
            if temps.get(key):
                return float(temps[key][0].current)
        return None

    def gpu(self) -> GPUStats:
        if self._nvml is not None:
            try:
                nv = self._nvml
                h = nv.nvmlDeviceGetHandleByIndex(0)
                mem = nv.nvmlDeviceGetMemoryInfo(h)
                name = nv.nvmlDeviceGetName(h)
                return GPUStats(
                    name=name.decode() if isinstance(name, bytes) else name,
                    total_memory_mb=int(mem.total / 1024 / 1024),
                    usage=float(nv.nvmlDeviceGetUtilizationRates(h).gpu),
                    memory_usage=round(mem.used / mem.total * 100, 1),
                    temperature=float(nv.nvmlDeviceGetTemperature(h, nv.NVML_TEMPERATURE_GPU)),
                )
            except Exception:
                logger.debug("NVML query failed", exc_info=True)
        if shutil.which("nvidia-smi"):
            return self._nvidia_smi()
        return GPUStats()

    @staticmethod
    def _nvidia_smi() -> GPUStats:
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,utilization.gpu,memory.used,temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3, check=True,
            ).stdout.splitlines()[0]
            name, total, util, used, temp = (x.strip() for x in out.split(","))
            return GPUStats(
                name=name, total_memory_mb=int(float(total)), usage=float(util),
                memory_usage=round(float(used) / float(total) * 100, 1), temperature=float(temp),
            )
        except Exception:
            return GPUStats()

    @staticmethod
    def hostname() -> str:
        return socket.gethostname()

    @staticmethod
    def primary_ip() -> str | None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("10.255.255.255", 1))  # no packet is sent
                return s.getsockname()[0]
        except OSError:
            return None
