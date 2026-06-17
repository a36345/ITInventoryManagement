"""
Monitorização de rede — banda larga (entrada/saída) e ping a router/firewall.
Corre em background; amostras guardadas em SQLite.
"""

import logging
import platform
import re
import subprocess
import threading
import time

import core.database as db
from core.discovery import _icmp_ping

log = logging.getLogger("ITInventory.network")

_CREATE_NO_WINDOW = 0x08000000

_PSUTIL = None
try:
    import psutil
    _PSUTIL = psutil
except ImportError:
    pass

_GATEWAY_CACHE = None
_GATEWAY_CACHE_TS = 0.0
_GATEWAY_TTL = 600.0
_prune_counter = 0


def detect_default_gateway():
    """Deteta o IP do gateway predefinido do sistema (com cache)."""
    global _GATEWAY_CACHE, _GATEWAY_CACHE_TS
    now = time.time()
    if _GATEWAY_CACHE and now - _GATEWAY_CACHE_TS < _GATEWAY_TTL:
        return _GATEWAY_CACHE
    ip = _detect_default_gateway_uncached()
    if ip:
        _GATEWAY_CACHE = ip
        _GATEWAY_CACHE_TS = now
    return ip


def _detect_default_gateway_uncached():
    try:
        if platform.system() == "Windows":
            kw = {"creationflags": _CREATE_NO_WINDOW}
            out = subprocess.check_output(["ipconfig"], **kw).decode(errors="replace")
            for line in out.splitlines():
                if "Gateway" in line and "." in line:
                    parts = line.strip().split(":")
                    if len(parts) > 1:
                        ip = parts[-1].strip()
                        if ip and ip[0].isdigit():
                            return ip
        else:
            out = subprocess.check_output(
                ["ip", "route"], stderr=subprocess.DEVNULL
            ).decode(errors="replace")
            m = re.search(r"default via (\d+\.\d+\.\d+\.\d+)", out)
            if m:
                return m.group(1)
    except Exception as e:
        log.debug("Gateway detection failed: %s", e)
    return None


def _resolve_targets():
    """Lista de (key, label, ip) a monitorizar."""
    gw = (db.get_setting("network_gateway_ip") or "").strip()
    fw = (db.get_setting("network_firewall_ip") or "").strip()
    if not gw:
        gw = detect_default_gateway() or ""
    targets = []
    if gw:
        targets.append(("gateway", "Router / Gateway", gw))
    if fw and fw != gw:
        targets.append(("firewall", "Firewall", fw))
    return targets


class NetworkMonitor:
    """Amostra banda e faz ping a router/FW em intervalo configurável."""

    def __init__(self, sample_callback=None):
        self.sample_callback = sample_callback or (lambda _data: None)
        self._stop = threading.Event()
        self._thread = None
        self._prev_counters = None
        self._prev_time = None
        self._last_online = {}
        self._started = False

    def start(self):
        if db.get_setting("background_monitors", "1") != "1":
            log.info("NetworkMonitor desactivado (background_monitors=0)")
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="NetworkMonitor")
        self._thread.start()
        self._started = True
        log.info("NetworkMonitor iniciado (psutil=%s)", bool(_PSUTIL))

    def stop(self):
        self._stop.set()

    def _loop(self):
        global _prune_counter
        while not self._stop.is_set():
            try:
                interval = max(60, int(db.get_setting("network_monitor_interval_s", "120")))
                self._sample_bandwidth()
                self._ping_targets()
                _prune_counter += 1
                if _prune_counter >= 30:
                    db.prune_network_history(days=7)
                    _prune_counter = 0
            except Exception as e:
                log.error("NetworkMonitor ciclo: %s", e)
                interval = max(60, int(db.get_setting("network_monitor_interval_s", "120")))
            self._stop.wait(interval)

    def _sample_bandwidth(self):
        if not _PSUTIL:
            return
        counters = _PSUTIL.net_io_counters()
        now = time.time()
        if self._prev_counters is not None and self._prev_time:
            dt = now - self._prev_time
            if dt > 0.5:
                down_bps = (counters.bytes_recv - self._prev_counters.bytes_recv) * 8 / dt
                up_bps = (counters.bytes_sent - self._prev_counters.bytes_sent) * 8 / dt
                down_mbps = round(max(0, down_bps) / 1_000_000, 2)
                up_mbps = round(max(0, up_bps) / 1_000_000, 2)
                db.record_network_metric(
                    counters.bytes_recv, counters.bytes_sent, down_mbps, up_mbps
                )
                self.sample_callback({
                    "down_mbps": down_mbps,
                    "up_mbps": up_mbps,
                })
        self._prev_counters = counters
        self._prev_time = now

    def _ping_targets(self):
        for key, label, ip in _resolve_targets():
            online, ms = _icmp_ping(ip, timeout=1.0)
            db.record_network_ping(key, label, ip, online, ms)
            was = self._last_online.get(key)
            self._last_online[key] = online
            if was is not None and was and not online:
                db.create_alert(
                    "Critical", "Network",
                    f"{label} offline ({ip})",
                    f"Sem resposta ao ping em {ip}",
                )


def get_live_status() -> dict:
    """Estado actual para API/UI (última amostra + pings)."""
    metric = db.get_latest_network_metric()
    pings = db.get_latest_network_pings()
    gw_cfg = (db.get_setting("network_gateway_ip") or "").strip()
    targets = _resolve_targets()
    configured = {
        "gateway_ip": gw_cfg or detect_default_gateway() or "",
        "firewall_ip": (db.get_setting("network_firewall_ip") or "").strip(),
        "interval_s": int(db.get_setting("network_monitor_interval_s", "120")),
        "psutil_available": bool(_PSUTIL),
    }
    return {
        "bandwidth": dict(metric) if metric else None,
        "pings": [dict(p) for p in pings],
        "targets": [{"key": k, "label": l, "ip": i} for k, l, i in targets],
        "config": configured,
    }
