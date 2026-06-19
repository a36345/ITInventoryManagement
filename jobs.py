"""
Tarefas agendadas — discovery, polling SNMP impressoras, sync AD.

Detecção automática de substituição de consumíveis:
  Se toner estava abaixo do limiar de alerta e agora está ≥ 50%
  → consumível foi substituído → desconta 1 do stock → alerta + email se stock baixo.
"""

import logging
import urllib.parse

from core.database import (
    get_setting, get_all_assets, upsert_printer, invalidate_caches,
    find_consumables_for_printer, decrement_consumable_stock,
    create_alert,
)
from core.discovery import DiscoveryEngine
from core.ad_sync import sync_ad_to_inventory

log = logging.getLogger("ITInventory.jobs")


# ── Discovery ─────────────────────────────────────────────────────────────────

def run_scheduled_discovery(subnet: str = None) -> list:
    """Scan completo de rede (para agendador ou worker autónomo)."""
    log.info("Discovery agendado a iniciar...")
    engine = DiscoveryEngine(
        progress_callback=lambda _p, _m: None,
        log_callback=lambda msg, level="info": log.info("[%s] %s", level, msg),
    )
    subnet = subnet or get_setting("subnet", "192.168.163.0/24")
    results = engine.run_full_discovery(subnet)
    if get_setting("ad_sync_enabled", "1") == "1":
        try:
            sync_ad_to_inventory()
        except Exception as e:
            log.warning("AD sync após discovery: %s", e)
    invalidate_caches()
    log.info("Discovery agendado concluído: %s dispositivos", len(results))
    return results


# ── Printer SNMP poll ──────────────────────────────────────────────────────────

# Mapeamento cor interna → (nome PT, tipo de consumível)
_COLORS = {
    "black":   ("Preto",   "Toner Preto"),
    "cyan":    ("Cyan",    "Toner Cyan"),
    "magenta": ("Magenta", "Toner Magenta"),
    "yellow":  ("Amarelo", "Toner Amarelo"),
}


def run_printer_snmp_poll() -> int:
    """
    Polling SNMP de todas as impressoras inventariadas.

    Para cada impressora:
      1. Lê níveis SNMP actuais
      2. Compara com níveis anteriores (guardados na BD)
      3. Se cor passou de ≤ limiar para ≥ 50% → substituição detectada
         → desconta 1 do stock do consumível correspondente
         → se stock ficar baixo → email com links de compra
      4. Grava alertas de toner baixo se aplicável
    """
    from core.snmp_engine import SNMPEngine

    community  = get_setting("snmp_community", "public")
    alert_pct  = max(1, int(get_setting("toner_alert_pct", "15")))
    engine     = SNMPEngine(community=community, timeout=2.0, retries=1)
    printers   = get_all_assets(filter_type="Impressora")
    updated    = 0

    for p in printers:
        p = dict(p)  # sqlite3.Row não suporta .get()
        ip = p.get("ip_address")
        if not ip:
            continue
        try:
            data = engine.full_scan(ip)
            if not data.get("sys_descr"):
                continue

            toner = data.get("toner") or {}
            new_levels = {
                "black":   toner.get("black",   -1),
                "cyan":    toner.get("cyan",    -1),
                "magenta": toner.get("magenta", -1),
                "yellow":  toner.get("yellow",  -1),
            }
            old_levels = {
                "black":   _safe_int(p["toner_black"]),
                "cyan":    _safe_int(p["toner_cyan"]),
                "magenta": _safe_int(p["toner_magenta"]),
                "yellow":  _safe_int(p["toner_yellow"]),
            }

            # ── 1. Detetar substituições ────────────────────────────────────
            for color, (color_pt, cons_type) in _COLORS.items():
                old_v = old_levels[color]
                new_v = new_levels[color]
                # Ambos têm de ser valores válidos (≥ 0)
                if old_v < 0 or new_v < 0:
                    continue
                # Era baixo (≤ limiar) e agora está alto (≥ 50%) → substituição
                if old_v <= alert_pct and new_v >= 50:
                    _handle_replacement(p, color, color_pt, cons_type)

            # ── 2. Actualizar BD ────────────────────────────────────────────
            upsert_printer(p["id"], {
                "toner_black":   new_levels["black"],
                "toner_cyan":    new_levels["cyan"],
                "toner_magenta": new_levels["magenta"],
                "toner_yellow":  new_levels["yellow"],
                "total_pages":   data.get("total_pages") or 0,
            })

            # ── 3. Alertas de nível baixo ────────────────────────────────────
            _check_toner_alerts(p, new_levels, alert_pct)

            updated += 1
        except Exception as e:
            log.debug("SNMP poll %s: %s", ip, e)

    log.info("SNMP impressoras: %s/%s actualizadas", updated, len(printers))
    return updated


def _safe_int(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return -1


def _handle_replacement(printer: dict, color: str, color_pt: str, cons_type: str):
    """
    Processa a substituição de um consumível detectada automaticamente.

    1. Procura consumível compatível em stock
    2. Desconta 1 unidade
    3. Cria alerta de registo
    4. Se stock ficar baixo → envia email com links de compra
    """
    hostname = printer.get("hostname", "—")
    model    = printer.get("model", "")

    consumables = find_consumables_for_printer(model, hostname, cons_type)

    if consumables:
        cons = consumables[0]
        new_qty, stock_min = decrement_consumable_stock(cons["id"])
        log.info(
            "Substituição detectada: %s em %s → ref=%s stock=%d",
            color_pt, hostname, cons["reference"], new_qty,
        )
        create_alert(
            "Info", "Consumable",
            f"Toner {color_pt} substituído em {hostname}",
            f"Referência: {cons['reference']} | Stock restante: {new_qty} un.",
            printer["id"],
        )
        # Se stock ficou abaixo do mínimo → notificar onde comprar
        if new_qty < stock_min:
            _send_low_stock_email(cons, printer, new_qty, stock_min)
    else:
        # Consumível não associado → só regista
        log.info("Substituição detectada: Toner %s em %s (sem consumível associado)", color_pt, hostname)
        create_alert(
            "Info", "Consumable",
            f"Toner {color_pt} substituído em {hostname}",
            "Consumível não encontrado no stock. Adicione a referência em Consumíveis "
            "e preencha o campo 'Compatível com' com o hostname da impressora.",
            printer["id"],
        )


def _check_toner_alerts(printer: dict, levels: dict, alert_pct: int):
    """Cria alertas de toner baixo (sem duplicar alertas já abertos)."""
    hostname = printer.get("hostname", "—")
    for color, (color_pt, _) in _COLORS.items():
        level = levels.get(color, -1)
        if 0 <= level <= alert_pct:
            create_alert(
                "Warning", "LowToner",
                f"Toner {color_pt} baixo em {hostname} ({level}%)",
                f"IP: {printer.get('ip_address', '—')} | Nível: {level}% "
                f"(limiar: {alert_pct}%)",
                printer["id"],
            )


def _send_low_stock_email(consumable: dict, printer: dict, stock_qty: int, stock_min: int):
    """
    Envia email de stock baixo com links de compra para fornecedores portugueses.
    """
    ref      = consumable.get("reference", "—")
    cons_type= consumable.get("type", "—")
    compat   = consumable.get("compatible_with", "—")
    hostname = printer.get("hostname", "—")

    # URLs de pesquisa — não precisam de API, funcionam sempre
    ref_enc = urllib.parse.quote(ref)
    links = [
        ("Google Shopping PT",
         f"https://www.google.pt/search?q={ref_enc}+comprar&tbm=shop"),
        ("PC Diga (PT)",
         f"https://www.pcdiga.com/pesquisa?q={ref_enc}"),
        ("FNAC Portugal",
         f"https://www.fnac.pt/SearchResult/ResultList.aspx?Search={ref_enc}"),
        ("Amazon.es",
         f"https://www.amazon.es/s?k={ref_enc}"),
        ("Zon.pt",
         f"https://www.zon.pt/search?q={ref_enc}"),
        ("Worten",
         f"https://www.worten.pt/search?query={ref_enc}"),
    ]

    subject = f"[IT Inventory] ⚠ Stock baixo — {ref} ({stock_qty}/{stock_min})"

    body_lines = [
        "ALERTA DE STOCK BAIXO — IT Inventory",
        "=" * 45,
        "",
        f"Consumível  : {ref}",
        f"Tipo        : {cons_type}",
        f"Compatível  : {compat}",
        f"Stock actual: {stock_qty} unidade(s)  [mínimo configurado: {stock_min}]",
        "",
        f"Motivo: substituição automática detectada em {hostname}",
        "",
        "ONDE COMPRAR:",
        "─" * 35,
    ]
    for store, url in links:
        body_lines.append(f"• {store}:")
        body_lines.append(f"  {url}")
        body_lines.append("")

    body_lines += [
        "─" * 35,
        "Este email foi gerado automaticamente pelo IT Inventory.",
        "Para ajustar o limiar de alerta: Configurações → Stock mínimo.",
    ]

    body = "\n".join(body_lines)

    # Criar alerta na BD (garante registo mesmo que email falhe)
    create_alert(
        "Warning", "LowStock",
        f"Stock baixo: {ref} ({stock_qty}/{stock_min})",
        f"Substituição em {hostname} | Stock: {stock_qty}/{stock_min}",
        printer.get("id"),
    )

    # Enviar email se SMTP configurado
    try:
        from core.ai_engine import send_email
        send_email(subject, body)
        log.info("Email stock baixo enviado: %s (stock=%d)", ref, stock_qty)
    except Exception as e:
        log.warning("Email stock baixo %s: %s", ref, e)


# ── AD Sync ───────────────────────────────────────────────────────────────────

def run_ad_sync_job() -> dict:
    return sync_ad_to_inventory()
