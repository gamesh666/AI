"""python -m aivms_sim.seed"""

import logging

from aivms_sim.seed.demo_seed import SeedConfig, seed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s")
seed(SeedConfig.from_env())
