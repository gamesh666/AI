"""Simulated GPU telemetry for edge agents running on machines without an NVIDIA GPU.

CPU / memory / temperature stay real (psutil); the GPU values follow smooth, plausible curves so the
dashboard and device pages show meaningful data.
"""

from __future__ import annotations

import math
import os
import random
import time

from agent.telemetry.system_metrics import GPUStats, SystemMetrics


class SimulatedMetrics(SystemMetrics):
    def __init__(self) -> None:
        super().__init__()
        self._phase = random.uniform(0, 2 * math.pi)
        self._name = os.environ.get("SIM_GPU_NAME", "Simulated NVIDIA T4")
        self._memory_mb = int(os.environ.get("SIM_GPU_MEMORY_MB", "16384"))

    def gpu(self) -> GPUStats:
        t = time.monotonic() / 60 + self._phase
        usage = 45 + 20 * math.sin(t) + random.uniform(-4, 4)
        return GPUStats(
            name=self._name,
            total_memory_mb=self._memory_mb,
            usage=round(max(0.0, min(100.0, usage)), 1),
            memory_usage=round(35 + 10 * math.sin(t / 2) + random.uniform(-1, 1), 1),
            temperature=round(52 + 12 * math.sin(t) + random.uniform(-1, 1), 1),
        )
