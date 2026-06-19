"""
Agendador em background — discovery, SNMP impressoras, sync AD.
"""

import logging
import threading
import time

from core.database import get_setting
from core.jobs import run_scheduled_discovery, run_printer_snmp_poll, run_ad_sync_job

log = logging.getLogger("ITInventory.scheduler")


class JobScheduler:
    def __init__(self):
        self._stop = threading.Event()
        self._thread = None
        self._last_discovery = 0.0
        self._last_printer = 0.0
        self._last_ad = 0.0
        self._discovery_running = False

    def start(self, delay_first_discovery_s: int = 300):
        """delay_first_discovery_s: espera antes do 1.º scan automático (não bloquear arranque)."""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._last_discovery = time.time()  # não correr logo ao arrancar
        self._last_printer = time.time()
        self._last_ad = time.time()
        self._delay_first = delay_first_discovery_s
        self._thread = threading.Thread(target=self._loop, daemon=True, name="JobScheduler")
        self._thread.start()
        log.info("JobScheduler iniciado")

    def stop(self):
        self._stop.set()

    def _loop(self):
        # Espera inicial antes do primeiro discovery automático
        if self._stop.wait(self._delay_first):
            return

        while not self._stop.is_set():
            try:
                now = time.time()
                if get_setting("scheduled_discovery", "1") == "1":
                    hours = max(1, int(get_setting("discovery_interval_hours", "24")))
                    if now - self._last_discovery >= hours * 3600 and not self._discovery_running:
                        self._run_discovery_async()
                        self._last_discovery = now

                if get_setting("scheduled_printer_poll", "1") == "1":
                    mins = max(5, int(get_setting("printer_poll_interval_min", "15")))
                    if now - self._last_printer >= mins * 60:
                        run_printer_snmp_poll()
                        self._last_printer = now

                if get_setting("ad_sync_enabled", "1") == "1":
                    hours = max(1, int(get_setting("ad_sync_interval_hours", "6")))
                    if now - self._last_ad >= hours * 3600:
                        run_ad_sync_job()
                        self._last_ad = now
            except Exception as e:
                log.error("JobScheduler ciclo: %s", e)

            self._stop.wait(60)

    def _run_discovery_async(self):
        def task():
            self._discovery_running = True
            try:
                run_scheduled_discovery()
            finally:
                self._discovery_running = False

        threading.Thread(target=task, daemon=True, name="ScheduledDiscovery").start()
