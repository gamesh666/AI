import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level.upper(),
        stream=sys.stdout,
        format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
    )
    # quiet noisy libraries
    for name in ("uvicorn.access", "aiomqtt"):
        logging.getLogger(name).setLevel(logging.WARNING)
