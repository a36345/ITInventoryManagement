"""
Sincronização Active Directory / LDAP — enriquece ativos com OU/departamento e IP.
"""

import logging
import re
import subprocess
import platform

from core.database import get_setting, get_conn, upsert_asset

log = logging.getLogger("ITInventory.ad")

_CREATE_NO_WINDOW = 0x08000000


def _domain_to_base(domain: str) -> str:
    parts = [p.strip() for p in (domain or "").split(".") if p.strip()]
    if not parts:
        return "DC=sml,DC=com"
    return ",".join(f"DC={p}" for p in parts)


def _ou_to_department(dn: str) -> str:
    """Extrai OU de utilizador/computador (ex: OU=Producao,OU=Computers,...)."""
    if not dn:
        return None
    ous = re.findall(r"OU=([^,]+)", dn, re.I)
    skip = {"computers", "computer", "workstations", "servers", "domain controllers"}
    for ou in ous:
        if ou.lower() not in skip:
            return ou
    return ous[0] if ous else None


def fetch_ad_computers() -> list:
    """
    Lista computadores do AD: name, hostname, ip, os, department, dn.
    Tenta LDAP (ldap3); fallback PowerShell no Windows.
    """
    computers = _fetch_via_ldap()
    if computers:
        return computers
    if platform.system() == "Windows":
        return _fetch_via_powershell()
    return []


def _fetch_via_ldap() -> list:
    host = get_setting("dc_host", "").strip()
    user = get_setting("ad_user", "").strip()
    password = get_setting("ad_password", "")
    domain = get_setting("ad_domain", "sml.com").strip()
    if not host or not user or not password:
        return []
    try:
        import ldap3
    except ImportError:
        log.info("ldap3 não instalado — pip install ldap3")
        return []

    base = _domain_to_base(domain)
    results = []
    try:
        server = ldap3.Server(host, port=389, connect_timeout=5)
        conn = ldap3.Connection(server, user=user, password=password, auto_bind=True)
        conn.search(
            base,
            "(&(objectClass=computer)(objectCategory=computer))",
            attributes=["cn", "dNSHostName", "operatingSystem", "distinguishedName"],
        )
        for entry in conn.entries:
            hostname = str(getattr(entry, "dNSHostName", "") or entry.cn or "").split(".")[0].upper()
            if not hostname:
                continue
            dn = str(entry.entry_dn)
            results.append({
                "hostname": hostname,
                "name": str(entry.cn),
                "os_version": str(getattr(entry, "operatingSystem", "") or "") or None,
                "department": _ou_to_department(dn),
                "ip_address": None,
                "dn": dn,
            })
        conn.unbind()
        log.info("LDAP: %s computadores do AD", len(results))
    except Exception as e:
        log.warning("LDAP falhou: %s", e)
    return results


def _fetch_via_powershell() -> list:
    user = get_setting("ad_user", "").strip()
    password = get_setting("ad_password", "")
    if not user or not password:
        return []
    ps = """
$sec = ConvertTo-SecureString '%s' -AsPlainText -Force
$cred = New-Object PSCredential('%s', $sec)
Import-Module ActiveDirectory -ErrorAction SilentlyContinue
Get-ADComputer -Filter * -Credential $cred -Properties IPv4Address,DNSHostName,OperatingSystem,DistinguishedName |
  Select-Object Name,DNSHostName,IPv4Address,OperatingSystem,DistinguishedName |
  ConvertTo-Json -Compress
""" % (password.replace("'", "''"), user.replace("'", "''"))
    try:
        import json
        kw = {"creationflags": _CREATE_NO_WINDOW} if platform.system() == "Windows" else {}
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", ps],
            timeout=120,
            stderr=subprocess.DEVNULL,
            **kw,
        ).decode(errors="replace").strip()
        if not out:
            return []
        data = json.loads(out)
        if isinstance(data, dict):
            data = [data]
        results = []
        for row in data:
            hostname = (row.get("DNSHostName") or row.get("Name") or "").split(".")[0].upper()
            if not hostname:
                continue
            ips = row.get("IPv4Address")
            ip = None
            if isinstance(ips, list) and ips:
                ip = ips[0]
            elif isinstance(ips, str) and ips:
                ip = ips.split(",")[0].strip() if "," in ips else ips
            dn = row.get("DistinguishedName") or ""
            results.append({
                "hostname": hostname,
                "name": row.get("Name"),
                "ip_address": ip,
                "os_version": row.get("OperatingSystem"),
                "department": _ou_to_department(dn),
                "dn": dn,
            })
        log.info("PowerShell AD: %s computadores", len(results))
        return results
    except Exception as e:
        log.warning("PowerShell AD falhou: %s", e)
        return []


def sync_ad_to_inventory() -> dict:
    """
    Cruza computadores AD com assets por hostname ou IP.
    Devolve estatísticas {matched, updated, not_found}.
    """
    computers = fetch_ad_computers()
    stats = {"ad_total": len(computers), "matched": 0, "updated": 0, "not_found": 0}
    if not computers:
        return stats

    with get_conn() as c:
        assets = c.execute(
            "SELECT id, hostname, ip_address, department FROM assets"
        ).fetchall()
    by_host = {(a["hostname"] or "").upper(): dict(a) for a in assets if a["hostname"]}
    by_ip = {a["ip_address"]: dict(a) for a in assets if a["ip_address"]}

    for comp in computers:
        host = (comp.get("hostname") or "").upper()
        asset = by_host.get(host)
        if not asset and comp.get("ip_address"):
            asset = by_ip.get(comp["ip_address"])
        if not asset:
            stats["not_found"] += 1
            continue
        stats["matched"] += 1
        patch = {"id": asset["id"], "hostname": host or asset.get("hostname")}
        if comp.get("department") and comp["department"] != asset.get("department"):
            patch["department"] = comp["department"]
            stats["updated"] += 1
        if comp.get("os_version"):
            patch["os_version"] = comp["os_version"]
        if comp.get("ip_address") and not asset.get("ip_address"):
            patch["ip_address"] = comp["ip_address"]
            stats["updated"] += 1
        upsert_asset(patch)

    log.info("AD sync: %s", stats)
    return stats
