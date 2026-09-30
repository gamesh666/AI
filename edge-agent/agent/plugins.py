"""Optional plugins, loaded at startup from EDGE_PLUGINS.

A plugin is a module with a `register()` function that adds implementations to the agent's
registries (camera sources, detectors, metrics providers). This is how development/simulation code
extends the agent without production code importing it:

    EDGE_PLUGINS=aivms_sim.edge.plugin   # adds mock:// + file:// sources, the "mock" detector, simulated GPU
"""

from __future__ import annotations

import importlib
import logging

logger = logging.getLogger(__name__)


def load_plugins(modules: list[str]) -> None:
    for name in modules:
        module = importlib.import_module(name)
        register = getattr(module, "register", None)
        if not callable(register):
            raise RuntimeError(f"plugin '{name}' has no register() function")
        register()
        logger.info("plugin loaded: %s", name)
