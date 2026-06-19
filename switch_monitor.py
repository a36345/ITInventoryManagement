"""
Switch port monitor — polling SNMP em todos os switches conhecidos a cada 60 s.

Para cada porta calcula throughput (Mbps) a partir dos contadores de 64 bits
(ifHCInOctets / ifHCOutOctets), resistente a counter wrap.
Os dados são guardados na tabela switch_ports (snapshot mais recente).
"""

import logging
import threading
import time

import core.database as db
from core.snmp_engine import get_interfaces

log = logging.getLogger("ITInventory.switch_monitor")

# Intervalo entre polls (segundos).
# 60 s é o standard em SNMP polling; abaixo disso os contadores mal avançam.
_POLL_INTERVAL = 60


class SwitchMonitor:
    """
    Background thread que faz polling SNMP a todos os switches no inventário.

    Usa contadores de 64 bits (ifHCInOctets/ifHCOutOctets) e calcula
    throughput em Mbps entre amostras consecutivas.
    """

    def __init__(self):
        self._stop    = threading.Event()
        self._thread  = None
        self._started = False
        # Última amostra por (asset_id, if_index) → (in_octets, out_octets, ts)
        self._prev: dict = {}

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        if db.get_setting("background_monitors", "1") != "1":
            log.info("SwitchMonitor desactivado (background_monitors=0)")
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="SwitchMonitor"
        )
        self._thread.start()
        self._started = True
        log.info("SwitchMonitor iniciado")

    def stop(self):
        self._stop.set()

    # ── Main loop ─────────────────────────────────────────────────────────────

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._poll_all()
            except Exception as e:
                log.error("SwitchMonitor ciclo erro: %s", e)
            self._stop.wait(_POLL_INTERVAL)

    def _poll_all(self):
        community = db.get_setting("snmp_community", "public")
        with db.get_conn() as c:
            switches = c.execute(
                "SELECT id, ip_address, hostname FROM assets"
                " WHERE type='Switch' AND ip_address IS NOT NULL AND ip_address != ''"
            ).fetchall()

        if not switches:
            log.debug("SwitchMonitor: nenhum switch no inventário")
            return

        for sw in switches:
            try:
                self._poll_switch(
                    sw["id"], sw["ip_address"], sw["hostname"], community
                )
            except Exception as e:
                log.debug(
                    "SwitchMonitor %s (%s): %s",
                    sw["hostname"], sw["ip_address"], e,
                )

    def _poll_switch(self, asset_id: int, ip: str, hostname: str, community: str):
        interfaces = get_interfaces(ip, community=community, timeout=2.0)
        if not interfaces:
            log.debug("Switch %s (%s): sem resposta SNMP", hostname, ip)
            return

        now = time.monotonic()
        polled = 0

        for iface in interfaces:
            idx = iface["index"]
            key = (asset_id, idx)
            prev = self._prev.get(key)

            in_mbps  = None
            out_mbps = None

            if prev:
                prev_in, prev_out, prev_ts = prev
                dt = now - prev_ts
                if dt >= 5:                           # mínimo 5 s de intervalo
                    in_diff  = iface["in_octets"]  - prev_in
                    out_diff = iface["out_octets"] - prev_out
                    # Resistência a wrap de contador 64-bit
                    if in_diff  < 0: in_diff  += 2 ** 64
                    if out_diff < 0: out_diff += 2 ** 64
                    in_mbps  = round(in_diff  * 8 / dt / 1_000_000, 3)
                    out_mbps = round(out_diff * 8 / dt / 1_000_000, 3)

            self._prev[key] = (iface["in_octets"], iface["out_octets"], now)

            db.upsert_switch_port(asset_id, idx, {
                "if_name":     iface["name"],
                "if_alias":    iface["alias"],
                "oper_status": iface["oper_status"],
                "speed_mbps":  iface["speed_mbps"],
                "in_octets":   iface["in_octets"],
                "out_octets":  iface["out_octets"],
                "in_mbps":     in_mbps,
                "out_mbps":    out_mbps,
            })
            polled += 1

        log.debug("Switch %s: %d portas actualizadas", hostname, polled)
