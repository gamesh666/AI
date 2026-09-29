"""Entry point:  python -m agent.main"""

from __future__ import annotations

import logging
import signal
import sys
import threading

from agent.config import get_settings
from agent.core.agent import EdgeAgent


def main() -> int:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        stream=sys.stdout,
        format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
    )
    # httpx logs full URLs at INFO, which would include presigned upload signatures
    logging.getLogger("httpx").setLevel(logging.WARNING)
    agent = EdgeAgent(settings)
    stopped = threading.Event()

    def _shutdown(signum, _frame) -> None:
        if not stopped.is_set():
            stopped.set()
            agent.stop()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    try:
        agent.run()
    finally:
        _shutdown(None, None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
