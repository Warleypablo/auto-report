from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger(__name__)


def alert(resumo: dict) -> None:
    """Envia webhook se ETL falhou em >10% dos clientes. Sem webhook configurado, é noop."""
    url = os.getenv("ETL_ALERT_WEBHOOK_URL")
    if not url:
        return

    fail = resumo.get("fail", 0)
    total = resumo.get("total", 0)
    if total == 0 or fail == 0:
        return

    pct = fail / total
    if pct < 0.1:
        return

    msg = f"⚠️ ETL vitrine: {fail}/{total} clientes falharam ({pct:.0%})"
    try:
        httpx.post(url, json={"text": msg}, timeout=10)
    except Exception:
        log.exception("falha_envio_alerta")
