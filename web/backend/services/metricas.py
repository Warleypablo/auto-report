from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session


def build_timeline(cliente_id: uuid.UUID, meses: int, session: Session) -> list[dict]:
    """Snapshots MENSAL dos últimos N meses, ordem cronológica (antigo → recente).

    Retorna a estrutura interna que os controllers usam para montar o response
    final (gestor inclui campos extras, cliente filtra os internos).
    """
    from models.snapshot import Snapshot

    snapshots = session.execute(
        select(Snapshot)
        .where(Snapshot.cliente_id == cliente_id, Snapshot.frequencia == "MENSAL")
        .order_by(Snapshot.periodo_fim.desc())
        .limit(meses)
    ).scalars().all()

    snapshots = list(reversed(snapshots))

    return [
        {
            "mes": s.periodo_fim.strftime("%Y-%m"),
            "periodo_inicio": str(s.periodo_inicio),
            "periodo_fim": str(s.periodo_fim),
            "faturamento": float(s.faturamento) if s.faturamento is not None else None,
            "investimento": float(s.investimento) if s.investimento is not None else None,
            "roas": float(s.roas) if s.roas is not None else None,
            "cpa": float(s.cpa) if s.cpa is not None else None,
            "leads": s.leads,
            "vendas": s.vendas,
            "faturamento_var_pct": float(s.faturamento_var_pct) if s.faturamento_var_pct is not None else None,
            "roas_var_pct": float(s.roas_var_pct) if s.roas_var_pct is not None else None,
        }
        for s in snapshots
    ]


def _parse_br(v: str | None) -> float | None:
    """Parse PT-BR formatted number like 'R$ 1.026,12' or '17,15'."""
    if not v or v.strip() in ("-", ""):
        return None
    try:
        cleaned = v.replace("R$", "").replace("\xa0", "").strip()
        cleaned = cleaned.replace(".", "").replace(",", ".")
        return float(cleaned)
    except (ValueError, AttributeError):
        return None


def _parse_int_br(v: str | None) -> int | None:
    if not v or v.strip() in ("-", ""):
        return None
    try:
        return int(v.replace(".", "").replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def build_breakdown(cliente_id: uuid.UUID, mes: str | None, session: Session) -> dict:
    """Top anúncios Meta + Google do snapshot mensal mais recente do cliente
    (ou do mês específico se passado).
    """
    from datetime import date, timedelta

    from models.snapshot import Snapshot

    snap_filter = [Snapshot.cliente_id == cliente_id, Snapshot.frequencia == "MENSAL"]
    if mes:
        ano, mes_num = int(mes[:4]), int(mes[5:7])
        primeiro = date(ano, mes_num, 1)
        if mes_num == 12:
            ultimo = date(ano + 1, 1, 1) - timedelta(days=1)
        else:
            ultimo = date(ano, mes_num + 1, 1) - timedelta(days=1)
        snap_filter.append(Snapshot.periodo_fim >= primeiro)
        snap_filter.append(Snapshot.periodo_fim <= ultimo)

    snap = session.execute(
        select(Snapshot).where(*snap_filter).order_by(Snapshot.periodo_fim.desc())
    ).scalars().first()

    if not snap or not snap.raw_dados:
        return {"meta_ads": [], "google_ads": []}

    rd = snap.raw_dados

    meta_ads = []
    for i in range(1, 21):
        nome = rd.get(f"{{{{nome_adf{i}}}}}", "")
        if not nome or nome == "-":
            continue
        img = rd.get(f"{{{{img_adf{i}}}}}", "") or ""
        meta_ads.append({
            "nome": nome,
            "investimento": _parse_br(rd.get(f"{{{{inv_adf{i}}}}}")),
            "leads": _parse_int_br(rd.get(f"{{{{lead_adf{i}}}}}")),
            "cpl": _parse_br(rd.get(f"{{{{cpl_adf{i}}}}}")),
            "conversoes": _parse_int_br(rd.get(f"{{{{conv_adf{i}}}}}")),
            "faturamento": _parse_br(rd.get(f"{{{{fat_adf{i}}}}}")),
            "roas": _parse_br(rd.get(f"{{{{roas_adf{i}}}}}")),
            "cpa": _parse_br(rd.get(f"{{{{cpa_adf{i}}}}}")),
            "impressoes": _parse_int_br(rd.get(f"{{{{imp_adf{i}}}}}")),
            "imagem_url": img if img not in ("__NO_IMAGE__", "-", "") else None,
        })

    google_ads = []
    for i in range(1, 21):
        nome = rd.get(f"{{{{nome_adg{i}}}}}", "")
        if not nome or nome == "-":
            continue
        google_ads.append({
            "nome": nome,
            "investimento": _parse_br(rd.get(f"{{{{inv_adg{i}}}}}")),
            "faturamento": _parse_br(rd.get(f"{{{{fat_adg{i}}}}}")),
            "conversoes": _parse_br(rd.get(f"{{{{conv_adg{i}}}}}")),
            "cpa": _parse_br(rd.get(f"{{{{cpa_adg{i}}}}}")),
            "roas": _parse_br(rd.get(f"{{{{roas_adg{i}}}}}")),
            "impressoes": _parse_int_br(rd.get(f"{{{{imp_adg{i}}}}}")),
        })

    return {"meta_ads": meta_ads, "google_ads": google_ads}


def meses_disponiveis_for_cliente(cliente_id: uuid.UUID, session: Session) -> list[str]:
    """Meses (YYYY-MM, DESC) que têm snapshot MENSAL para o cliente."""
    rows = session.execute(
        text("""
            SELECT DISTINCT TO_CHAR(periodo_fim, 'YYYY-MM') AS mes
            FROM snapshots
            WHERE frequencia = 'MENSAL' AND cliente_id = :cid
            ORDER BY mes DESC
        """),
        {"cid": cliente_id},
    ).all()
    return [r[0] for r in rows]
