import sqlite3
import os
import time
import hashlib
import secrets
from datetime import datetime
from pathlib import Path

DB_PATH = Path(os.environ.get("ITINV_DB", Path.home() / "ITInventory" / "inventory.db"))

_SETTINGS_CACHE: dict = {}
_SETTINGS_CACHE_TS = 0.0
_SETTINGS_TTL = 45.0
_STATS_CACHE: dict | None = None
_STATS_CACHE_TS = 0.0
_STATS_TTL = 20.0

# ── Password helpers ──────────────────────────────────────────────────────────

def _hash_password(password: str) -> tuple:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100_000)
    return dk.hex(), salt

def _verify_password(password: str, stored_hash: str, salt: str) -> bool:
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100_000)
    return dk.hex() == stored_hash

def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    with get_conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS assets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            hostname    TEXT NOT NULL,
            type        TEXT NOT NULL DEFAULT 'Desktop',
            status      TEXT NOT NULL DEFAULT 'Online',
            ip_address  TEXT,
            mac_address TEXT,
            manufacturer TEXT,
            model       TEXT,
            serial_number TEXT,
            department  TEXT,
            assigned_user TEXT,
            os_version  TEXT,
            acquisition_year INTEGER,
            purchase_price REAL,
            purchase_date TEXT,
            supplier    TEXT,
            warranty_years INTEGER,
            warranty_end TEXT,
            notes       TEXT,
            confidence  REAL DEFAULT 1.0,
            needs_review INTEGER DEFAULT 0,
            last_seen   TEXT,
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS printers (
            asset_id    INTEGER PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
            toner_black INTEGER DEFAULT -1,
            toner_cyan  INTEGER DEFAULT -1,
            toner_magenta INTEGER DEFAULT -1,
            toner_yellow INTEGER DEFAULT -1,
            total_pages INTEGER DEFAULT 0,
            monthly_pages INTEGER DEFAULT 0,
            snmp_community TEXT DEFAULT 'public',
            last_poll   TEXT
        );
        CREATE TABLE IF NOT EXISTS consumables (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            reference   TEXT NOT NULL UNIQUE,
            type        TEXT,
            compatible_with TEXT,
            stock_qty   INTEGER DEFAULT 0,
            stock_min   INTEGER DEFAULT 2,
            updated_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            severity    TEXT NOT NULL,
            type        TEXT NOT NULL,
            title       TEXT NOT NULL,
            details     TEXT,
            asset_id    INTEGER REFERENCES assets(id) ON DELETE SET NULL,
            status      TEXT DEFAULT 'Open',
            email_sent  INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now')),
            resolved_at TEXT
        );
        CREATE TABLE IF NOT EXISTS device_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id    INTEGER REFERENCES assets(id) ON DELETE CASCADE,
            is_online   INTEGER,
            ping_ms     INTEGER,
            checked_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS network_metrics (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            bytes_recv  INTEGER NOT NULL,
            bytes_sent  INTEGER NOT NULL,
            down_mbps   REAL NOT NULL,
            up_mbps     REAL NOT NULL,
            checked_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS network_pings (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            target_key   TEXT NOT NULL,
            target_label TEXT,
            target_ip    TEXT NOT NULL,
            is_online    INTEGER NOT NULL,
            ping_ms      INTEGER,
            checked_at   TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS switch_ports (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id    INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
            if_index    INTEGER NOT NULL,
            if_name     TEXT,
            if_alias    TEXT,
            oper_status INTEGER DEFAULT 2,
            speed_mbps  INTEGER DEFAULT 0,
            in_octets   INTEGER DEFAULT 0,
            out_octets  INTEGER DEFAULT 0,
            in_mbps     REAL,
            out_mbps    REAL,
            checked_at  TEXT DEFAULT (datetime('now')),
            UNIQUE(asset_id, if_index)
        );
        CREATE INDEX IF NOT EXISTS idx_switch_ports_asset ON switch_ports(asset_id, if_index);
        CREATE INDEX IF NOT EXISTS idx_switch_ports_at    ON switch_ports(checked_at);
        CREATE INDEX IF NOT EXISTS idx_assets_ip  ON assets(ip_address);
        CREATE INDEX IF NOT EXISTS idx_network_metrics_at ON network_metrics(checked_at);
        CREATE INDEX IF NOT EXISTS idx_network_pings_key ON network_pings(target_key, checked_at);
        CREATE INDEX IF NOT EXISTS idx_assets_mac ON assets(mac_address);
        CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt          TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'normal',
            created_at    TEXT DEFAULT (datetime('now')),
            last_login    TEXT
        );
        """)
        # Default settings
        defaults = {
            "subnet":              "",
            "snmp_community":      "public",
            "snmp_timeout_ms":     "3000",
            "ping_interval_s":     "300",
            "ping_max_workers":    "8",
            "dc_host":             "",
            "ad_domain":           "",
            "ad_user":             "",
            "ad_password":         "",
            "smtp_host":           "",
            "smtp_port":           "587",
            "smtp_user":           "",
            "smtp_password":       "",
            "email_to":            "",
            "toner_alert_pct":     "15",
            "offline_alert_min":   "15",
            "web_api_key":         "",
            "ai_backend":          "ollama",
            "ollama_host":         "http://localhost:11434",
            "ollama_model":        "llama3.2",
            "ollama_vision_model": "llava",
            "anthropic_key":       "",
            "network_gateway_ip":  "",
            "network_firewall_ip": "",
            "network_monitor_interval_s": "120",
            "background_monitors":   "1",
            "discovery_use_ai":      "1",
            "scheduled_discovery":   "1",
            "discovery_interval_hours": "24",
            "scheduled_printer_poll": "1",
            "printer_poll_interval_min": "15",
            "ad_sync_enabled":       "1",
            "ad_sync_interval_hours": "6",
            "alert_email_enabled":   "1",
            "web_cors_origins":      "http://localhost:5050,http://127.0.0.1:5050,null",
            "ollama_num_ctx":        "2048",
            "ollama_num_threads":    "",
        }
        for k, v in defaults.items():
            c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))
        # Utilizador admin por omissão (só na 1.ª execução)
        if not c.execute("SELECT id FROM users LIMIT 1").fetchone():
            ph, salt = _hash_password("admin")
            c.execute(
                "INSERT OR IGNORE INTO users(username,password_hash,salt,role) VALUES(?,?,?,?)",
                ("admin", ph, salt, "admin")
            )

# ── Settings ──────────────────────────────────────────────────────────────────

def _load_settings_cache():
    global _SETTINGS_CACHE, _SETTINGS_CACHE_TS
    with get_conn() as c:
        _SETTINGS_CACHE = {r["key"]: r["value"] for r in c.execute("SELECT key, value FROM settings")}
    _SETTINGS_CACHE_TS = time.time()

def invalidate_caches():
    global _SETTINGS_CACHE_TS, _STATS_CACHE, _STATS_CACHE_TS
    _SETTINGS_CACHE_TS = 0.0
    _STATS_CACHE = None
    _STATS_CACHE_TS = 0.0

def get_setting(key: str, default: str = "") -> str:
    global _SETTINGS_CACHE_TS
    if time.time() - _SETTINGS_CACHE_TS > _SETTINGS_TTL:
        _load_settings_cache()
    return _SETTINGS_CACHE.get(key, default)

def set_setting(key: str, value: str):
    global _STATS_CACHE, _STATS_CACHE_TS
    with get_conn() as c:
        c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value))
    _SETTINGS_CACHE[key] = value
    _STATS_CACHE = None
    _STATS_CACHE_TS = 0.0

# ── Assets ────────────────────────────────────────────────────────────────────

def upsert_asset(data: dict) -> int:
    """Insert or update by MAC or IP. Returns asset id."""
    invalidate_caches()
    with get_conn() as c:
        existing = None
        if data.get("mac_address"):
            existing = c.execute(
                "SELECT id FROM assets WHERE mac_address=?",
                (data["mac_address"],)).fetchone()
        if not existing and data.get("ip_address"):
            existing = c.execute(
                "SELECT id FROM assets WHERE ip_address=?",
                (data["ip_address"],)).fetchone()

        data["updated_at"] = datetime.utcnow().isoformat()
        if existing:
            asset_id = existing["id"]
            fields = ", ".join(f"{k}=?" for k in data if k != "id")
            c.execute(f"UPDATE assets SET {fields} WHERE id=?",
                      list(data.values()) + [asset_id])
            return asset_id
        else:
            cols = ", ".join(data.keys())
            placeholders = ", ".join("?" * len(data))
            cur = c.execute(f"INSERT INTO assets({cols}) VALUES({placeholders})",
                            list(data.values()))
            return cur.lastrowid

def get_all_assets(filter_type=None, filter_dept=None, filter_status=None,
                   search=None, needs_review=None):
    with get_conn() as c:
        q = "SELECT a.*, p.toner_black, p.toner_cyan, p.toner_magenta, p.toner_yellow, p.total_pages, p.last_poll FROM assets a LEFT JOIN printers p ON a.id=p.asset_id WHERE 1=1"
        params = []
        if filter_type:   q += " AND a.type=?";       params.append(filter_type)
        if filter_dept:   q += " AND a.department=?"; params.append(filter_dept)
        if filter_status: q += " AND a.status=?";     params.append(filter_status)
        if needs_review is not None:
            q += " AND a.needs_review=?"; params.append(1 if needs_review else 0)
        if search:
            q += " AND (a.hostname LIKE ? OR a.ip_address LIKE ? OR a.model LIKE ? OR a.serial_number LIKE ?)"
            s = f"%{search}%"
            params += [s, s, s, s]
        q += " ORDER BY a.hostname"
        return c.execute(q, params).fetchall()

def get_asset(asset_id: int):
    with get_conn() as c:
        return c.execute(
            "SELECT a.*, p.toner_black, p.toner_cyan, p.toner_magenta, p.toner_yellow, p.total_pages, p.monthly_pages, p.last_poll FROM assets a LEFT JOIN printers p ON a.id=p.asset_id WHERE a.id=?",
            (asset_id,)).fetchone()

def delete_asset(asset_id: int):
    with get_conn() as c:
        c.execute("DELETE FROM assets WHERE id=?", (asset_id,))

def delete_all_assets() -> int:
    """Remove todos os ativos (e cascata para printers/history). Retorna quantidade eliminada."""
    with get_conn() as c:
        count = c.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        c.execute("DELETE FROM assets")
    invalidate_caches()
    return count

def get_stats():
    global _STATS_CACHE, _STATS_CACHE_TS
    now = time.time()
    if _STATS_CACHE is not None and now - _STATS_CACHE_TS < _STATS_TTL:
        return _STATS_CACHE
    with get_conn() as c:
        total   = c.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        online  = c.execute("SELECT COUNT(*) FROM assets WHERE status='Online'").fetchone()[0]
        offline = c.execute("SELECT COUNT(*) FROM assets WHERE status='Offline'").fetchone()[0]
        review  = c.execute("SELECT COUNT(*) FROM assets WHERE needs_review=1").fetchone()[0]
        replace = c.execute(
            "SELECT COUNT(*) FROM assets WHERE type IN ('Desktop','Laptop') AND acquisition_year IS NOT NULL AND (strftime('%Y','now')-acquisition_year)>=4"
        ).fetchone()[0]
        alerts_open = c.execute("SELECT COUNT(*) FROM alerts WHERE status='Open'").fetchone()[0]
        _STATS_CACHE = dict(total=total, online=online, offline=offline,
                            review=review, replace=replace, alerts_open=alerts_open)
        _STATS_CACHE_TS = now
        return _STATS_CACHE

def get_ping_targets():
    """IDs e IPs para ping — query leve, sem JOIN."""
    with get_conn() as c:
        return c.execute(
            "SELECT id, ip_address FROM assets WHERE ip_address IS NOT NULL AND ip_address != ''"
        ).fetchall()

def get_lifecycle_report():
    with get_conn() as c:
        return c.execute("""
            SELECT acquisition_year, COUNT(*) as cnt,
                   (strftime('%Y','now') - acquisition_year) as age
            FROM assets
            WHERE type IN ('Desktop','Laptop') AND acquisition_year IS NOT NULL
            GROUP BY acquisition_year ORDER BY acquisition_year DESC
        """).fetchall()

# ── Printers ──────────────────────────────────────────────────────────────────

def upsert_printer(asset_id: int, data: dict):
    data["asset_id"] = asset_id
    data["last_poll"] = datetime.utcnow().isoformat()
    with get_conn() as c:
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" * len(data))
        updates = ", ".join(f"{k}=excluded.{k}" for k in data if k != "asset_id")
        c.execute(f"""
            INSERT INTO printers({cols}) VALUES({placeholders})
            ON CONFLICT(asset_id) DO UPDATE SET {updates}
        """, list(data.values()))

def get_critical_printers():
    thr = int(get_setting("toner_alert_pct", "15"))
    with get_conn() as c:
        return c.execute(f"""
            SELECT a.hostname, a.ip_address, p.*
            FROM printers p JOIN assets a ON a.id=p.asset_id
            WHERE (p.toner_black BETWEEN 0 AND {thr})
               OR (p.toner_cyan BETWEEN 0 AND {thr})
               OR (p.toner_magenta BETWEEN 0 AND {thr})
               OR (p.toner_yellow BETWEEN 0 AND {thr})
        """).fetchall()

# ── Consumables ───────────────────────────────────────────────────────────────

def get_all_consumables():
    with get_conn() as c:
        return c.execute("SELECT * FROM consumables ORDER BY reference").fetchall()

def upsert_consumable(data: dict):
    data["updated_at"] = datetime.utcnow().isoformat()
    with get_conn() as c:
        cols = ", ".join(data.keys())
        ph   = ", ".join("?" * len(data))
        upd  = ", ".join(f"{k}=excluded.{k}" for k in data if k != "reference")
        c.execute(f"INSERT INTO consumables({cols}) VALUES({ph}) ON CONFLICT(reference) DO UPDATE SET {upd}",
                  list(data.values()))

def get_low_stock_consumables():
    with get_conn() as c:
        return c.execute(
            "SELECT * FROM consumables WHERE stock_qty < stock_min ORDER BY stock_qty"
        ).fetchall()

def find_consumables_for_printer(model: str, hostname: str, consumable_type: str) -> list:
    """
    Encontra consumíveis em stock compatíveis com a impressora dada.

    Estratégia de match (por ordem de preferência):
      1. compatible_with contém o hostname exacto da impressora
      2. compatible_with contém parte do modelo
    O tipo do consumível (Toner Preto / Tambor / etc.) tem de corresponder.
    """
    with get_conn() as c:
        rows = c.execute(
            "SELECT * FROM consumables WHERE stock_qty > 0 ORDER BY stock_qty DESC"
        ).fetchall()

    type_kw = (consumable_type or "").lower()
    hn = (hostname or "").lower()
    mod = (model or "").lower()
    # Palavras-chave de cor do tipo de consumível
    color_kw = {
        "preto": ("preto", "black", "bk", "noir"),
        "cyan":  ("cyan",  "blue",  "azul"),
        "magenta": ("magenta", "red", "vermelho"),
        "amarelo": ("amarelo", "yellow", "jaune"),
    }
    # Que cor estamos à procura?
    target_colors = None
    for col, kws in color_kw.items():
        if any(k in type_kw for k in kws):
            target_colors = kws
            break

    matches = []
    for row in rows:
        compat = (row["compatible_with"] or "").lower()
        rtype  = (row["type"] or "").lower()
        if not compat:
            continue
        # Verificar tipo/cor
        if target_colors and not any(k in rtype for k in target_colors):
            continue
        # Verificar compatibilidade com a impressora
        if hn and hn in compat:
            matches.insert(0, dict(row))  # hostname match → prioridade máxima
        elif mod and any(part in compat for part in mod.split() if len(part) > 3):
            matches.append(dict(row))
    return matches

def decrement_consumable_stock(consumable_id: int) -> int:
    """Desconta 1 unidade do stock. Nunca vai abaixo de 0. Retorna stock resultante."""
    with get_conn() as c:
        c.execute(
            "UPDATE consumables SET stock_qty = MAX(0, stock_qty - 1),"
            " updated_at = datetime('now') WHERE id = ?",
            (consumable_id,),
        )
        row = c.execute(
            "SELECT stock_qty, stock_min FROM consumables WHERE id = ?",
            (consumable_id,),
        ).fetchone()
    invalidate_caches()
    return (row["stock_qty"], row["stock_min"]) if row else (0, 0)

# ── Alerts ────────────────────────────────────────────────────────────────────

def create_alert(severity, type_, title, details=None, asset_id=None):
    with get_conn() as c:
        existing = c.execute(
            "SELECT id FROM alerts WHERE asset_id=? AND type=? AND status='Open'",
            (asset_id, type_)).fetchone()
        if existing:
            return existing["id"]
        cur = c.execute(
            "INSERT INTO alerts(severity,type,title,details,asset_id) VALUES(?,?,?,?,?)",
            (severity, type_, title, details, asset_id))
        alert_id = cur.lastrowid

    hostname = None
    if asset_id:
        with get_conn() as c:
            row = c.execute("SELECT hostname FROM assets WHERE id=?", (asset_id,)).fetchone()
            if row:
                hostname = row["hostname"]
    try:
        from core.notifications import send_alert_email
        send_alert_email(alert_id, severity, type_, title, details, hostname)
    except Exception:
        pass
    invalidate_caches()
    return alert_id


def mark_alert_email_sent(alert_id: int):
    with get_conn() as c:
        c.execute("UPDATE alerts SET email_sent=1 WHERE id=?", (alert_id,))

def get_open_alerts():
    with get_conn() as c:
        return c.execute("""
            SELECT al.*, a.hostname FROM alerts al
            LEFT JOIN assets a ON a.id=al.asset_id
            WHERE al.status='Open' ORDER BY al.created_at DESC
        """).fetchall()

def resolve_alert(alert_id: int):
    with get_conn() as c:
        c.execute("UPDATE alerts SET status='Resolved', resolved_at=datetime('now') WHERE id=?",
                  (alert_id,))

# ── Device history ────────────────────────────────────────────────────────────

def record_ping(asset_id: int, is_online: bool, ping_ms: int = None):
    record_pings_batch([(asset_id, is_online, ping_ms)])

def record_pings_batch(results: list):
    """Grava vários pings numa única transacção."""
    if not results:
        return
    invalidate_caches()
    with get_conn() as c:
        c.executemany(
            "INSERT INTO device_history(asset_id,is_online,ping_ms) VALUES(?,?,?)",
            [(aid, 1 if on else 0, ms) for aid, on, ms in results],
        )
        online_ids = [aid for aid, on, _ in results if on]
        offline_ids = [aid for aid, on, _ in results if not on]
        if online_ids:
            ph = ",".join("?" * len(online_ids))
            c.execute(
                f"UPDATE assets SET status='Online', last_seen=datetime('now') WHERE id IN ({ph})",
                online_ids,
            )
        if offline_ids:
            ph = ",".join("?" * len(offline_ids))
            c.execute(f"UPDATE assets SET status='Offline' WHERE id IN ({ph})", offline_ids)

def get_uptime_24h(asset_id: int):
    with get_conn() as c:
        rows = c.execute("""
            SELECT is_online FROM device_history
            WHERE asset_id=? AND checked_at >= datetime('now','-24 hours')
            ORDER BY checked_at
        """, (asset_id,)).fetchall()
        if not rows: return None
        pct = sum(r["is_online"] for r in rows) / len(rows) * 100
        return round(pct, 1)

# ── Network monitoring ────────────────────────────────────────────────────────

def record_network_metric(bytes_recv: int, bytes_sent: int, down_mbps: float, up_mbps: float):
    with get_conn() as c:
        c.execute(
            "INSERT INTO network_metrics(bytes_recv, bytes_sent, down_mbps, up_mbps) VALUES(?,?,?,?)",
            (bytes_recv, bytes_sent, down_mbps, up_mbps),
        )

def get_latest_network_metric():
    with get_conn() as c:
        return c.execute(
            "SELECT * FROM network_metrics ORDER BY checked_at DESC LIMIT 1"
        ).fetchone()

def get_network_metrics_history(hours: int = 24, limit: int = 72):
    with get_conn() as c:
        return c.execute(
            """SELECT down_mbps, up_mbps, bytes_recv, bytes_sent, checked_at
               FROM network_metrics
               WHERE checked_at >= datetime('now', ?)
               ORDER BY checked_at DESC
               LIMIT ?""",
            (f"-{hours} hours", limit),
        ).fetchall()

def record_network_ping(target_key: str, target_label: str, target_ip: str,
                        is_online: bool, ping_ms: int = None):
    with get_conn() as c:
        c.execute(
            """INSERT INTO network_pings(target_key, target_label, target_ip, is_online, ping_ms)
               VALUES(?,?,?,?,?)""",
            (target_key, target_label, target_ip, 1 if is_online else 0, ping_ms),
        )

def get_latest_network_pings():
    """Último ping por target_key."""
    with get_conn() as c:
        return c.execute("""
            SELECT p.* FROM network_pings p
            INNER JOIN (
                SELECT target_key, MAX(checked_at) AS mx
                FROM network_pings GROUP BY target_key
            ) latest ON p.target_key = latest.target_key AND p.checked_at = latest.mx
            ORDER BY p.target_key
        """).fetchall()

def get_network_ping_history(target_key: str, hours: int = 24):
    with get_conn() as c:
        return c.execute(
            """SELECT is_online, ping_ms, checked_at FROM network_pings
               WHERE target_key=? AND checked_at >= datetime('now', ?)
               ORDER BY checked_at""",
            (target_key, f"-{hours} hours"),
        ).fetchall()

def prune_network_history(days: int = 7):
    with get_conn() as c:
        c.execute(
            "DELETE FROM network_metrics WHERE checked_at < datetime('now', ?)",
            (f"-{days} days",),
        )
        c.execute(
            "DELETE FROM network_pings WHERE checked_at < datetime('now', ?)",
            (f"-{days} days",),
        )

# ── Switch port monitoring ─────────────────────────────────────────────────────

def upsert_switch_port(asset_id: int, if_index: int, data: dict):
    """Actualiza (ou insere) o snapshot mais recente de uma porta de switch."""
    data = dict(data)
    data["asset_id"]   = asset_id
    data["if_index"]   = if_index
    data["checked_at"] = datetime.utcnow().isoformat()
    with get_conn() as c:
        cols = ", ".join(data.keys())
        ph   = ", ".join("?" * len(data))
        upd  = ", ".join(
            f"{k}=excluded.{k}"
            for k in data if k not in ("asset_id", "if_index")
        )
        c.execute(
            f"INSERT INTO switch_ports({cols}) VALUES({ph})"
            f" ON CONFLICT(asset_id, if_index) DO UPDATE SET {upd}",
            list(data.values()),
        )

def get_switch_ports(asset_id: int) -> list:
    """Devolve todas as portas do switch com asset_id dado."""
    with get_conn() as c:
        return c.execute(
            "SELECT * FROM switch_ports WHERE asset_id=? ORDER BY if_index",
            (asset_id,),
        ).fetchall()

def get_all_switches_with_ports() -> list:
    """
    Devolve switches conhecidos com as suas portas.
    Formato: lista de (switch_row, [port_rows])
    """
    with get_conn() as c:
        switches = c.execute(
            "SELECT id, hostname, ip_address FROM assets"
            " WHERE type='Switch' AND ip_address IS NOT NULL AND ip_address != ''"
            " ORDER BY hostname"
        ).fetchall()
        result = []
        for sw in switches:
            ports = c.execute(
                "SELECT * FROM switch_ports WHERE asset_id=? ORDER BY if_index",
                (sw["id"],),
            ).fetchall()
            result.append((sw, ports))
    return result

# ── Users ─────────────────────────────────────────────────────────────────────

def get_all_users():
    with get_conn() as c:
        return c.execute(
            "SELECT id, username, role, created_at, last_login FROM users ORDER BY username"
        ).fetchall()

def verify_user(username: str, password: str):
    """Verifica credenciais. Devolve dict {id, username, role} ou None."""
    with get_conn() as c:
        row = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not row:
        return None
    if _verify_password(password, row["password_hash"], row["salt"]):
        with get_conn() as c:
            c.execute("UPDATE users SET last_login=datetime('now') WHERE id=?", (row["id"],))
        return {"id": row["id"], "username": row["username"], "role": row["role"]}
    return None

def create_user(username: str, password: str, role: str = "normal") -> int:
    ph, salt = _hash_password(password)
    with get_conn() as c:
        cur = c.execute(
            "INSERT INTO users(username,password_hash,salt,role) VALUES(?,?,?,?)",
            (username, ph, salt, role)
        )
        return cur.lastrowid

def update_user_password(user_id: int, new_password: str):
    ph, salt = _hash_password(new_password)
    with get_conn() as c:
        c.execute("UPDATE users SET password_hash=?,salt=? WHERE id=?", (ph, salt, user_id))

def update_user_role(user_id: int, role: str):
    with get_conn() as c:
        c.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))

def delete_user(user_id: int):
    with get_conn() as c:
        c.execute("DELETE FROM users WHERE id=?", (user_id,))
