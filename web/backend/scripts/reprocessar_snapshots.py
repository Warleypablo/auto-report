"""Reaplica `map_handler_dados` sobre `raw_dados` já gravados.

Útil quando o mapeamento muda e queremos atualizar todos os snapshots sem
re-bater nas APIs externas (Meta/Google/Sheets).
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT / "backend"))

from sqlalchemy import select  # noqa: E402
from db import SessionLocal  # noqa: E402
from etl.transform import map_handler_dados  # noqa: E402
from models import Snapshot  # noqa: E402


def main() -> dict:
    atualizados = 0
    sem_raw = 0
    inalterados = 0
    with SessionLocal() as s:
        snaps = list(s.scalars(select(Snapshot)).all())
        for snap in snaps:
            raw = snap.raw_dados or {}
            if not raw:
                sem_raw += 1
                continue
            novo = map_handler_dados(raw)
            mudou = False
            for campo in ("faturamento", "investimento", "roas", "cpa", "vendas", "leads"):
                v = novo.get(campo)
                if getattr(snap, campo) != v:
                    setattr(snap, campo, v)
                    mudou = True
            if novo.get("metricas_detalhadas") != snap.metricas_detalhadas:
                snap.metricas_detalhadas = novo["metricas_detalhadas"]
                mudou = True
            if mudou:
                atualizados += 1
            else:
                inalterados += 1
        s.commit()
    resumo = {"total": len(snaps), "atualizados": atualizados, "inalterados": inalterados, "sem_raw": sem_raw}
    print(resumo)
    return resumo


if __name__ == "__main__":
    main()
