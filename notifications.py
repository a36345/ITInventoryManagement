"""
Notificações — email automático quando um alerta novo é criado.
"""

import logging

from core.database import get_setting, mark_alert_email_sent

log = logging.getLogger("ITInventory.notifications")


def _smtp_configured() -> bool:
    return bool(
        get_setting("smtp_host")
        and get_setting("smtp_user")
        and get_setting("smtp_password")
        and get_setting("email_to")
    )


def send_alert_email(alert_id: int, severity: str, type_: str, title: str,
                     details: str = None, hostname: str = None) -> bool:
    """Envia email para alerta novo. Devolve True se enviado."""
    if get_setting("alert_email_enabled", "1") != "1":
        return False
    if not _smtp_configured():
        log.debug("SMTP não configurado — alerta %s sem email", alert_id)
        return False
    try:
        from core.ai_engine import send_email
        host_line = f"\nEquipamento: {hostname}" if hostname else ""
        body = (
            f"Alerta IT Inventory\n"
            f"{'=' * 40}\n"
            f"Prioridade: {severity}\n"
            f"Tipo: {type_}\n"
            f"Título: {title}\n"
            f"{host_line}\n"
        )
        if details:
            body += f"\nDetalhes:\n{details}\n"
        subject = f"[IT Inventory] {severity} — {title}"
        send_email(subject, body)
        mark_alert_email_sent(alert_id)
        log.info("Email enviado para alerta #%s", alert_id)
        return True
    except Exception as e:
        log.warning("Falha email alerta #%s: %s", alert_id, e)
        return False
