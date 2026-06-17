#!/usr/bin/env python
"""
Worker autónomo — discovery + sync AD (SO/SD).
Corre sem a UI desktop; partilha a mesma base SQLite.

Uso:
  python services/discovery_worker.py
  python services/discovery_worker.py --loop 24
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            Path(os.environ.get("ITINV_HOME", Path.home() / "ITInventory")) / "worker.log",
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger("discovery_worker")


def main():
    parser = argparse.ArgumentParser(description="IT Inventory — Discovery Worker")
    parser.add_argument(
        "--loop", type=float, default=0,
        help="Repetir a cada N horas (0 = uma vez)",
    )
    parser.add_argument("--subnet", default=None, help="Subnet (ex: 192.168.163.0/24)")
    args = parser.parse_args()

    import core.database as db
    from core.jobs import run_scheduled_discovery

    db.init_db()
    subnet = args.subnet or os.environ.get("ITINV_SUBNET")

    while True:
        try:
            results = run_scheduled_discovery(subnet)
            log.info("Concluído: %s dispositivos", len(results))
        except Exception as e:
            log.error("Discovery falhou: %s", e)

        if args.loop <= 0:
            break
        sleep_s = max(1.0, args.loop) * 3600
        log.info("Próximo scan em %.1f h", args.loop)
        time.sleep(sleep_s)


if __name__ == "__main__":
    main()
