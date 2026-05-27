from __future__ import annotations

import logging
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Callable

# Garante que core/ (raiz do auto-report) está no PYTHONPATH
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app_settings import get_settings
from db import SessionLocal, engine
from models import Categoria, Cliente
from models.snapshot import Frequencia

from .alerting import alert
from .cliente_publico import ClientePublico
from .lock import LockTaken, advisory_lock
from .transform import map_handler_dados
from .upsert import upsert_snapshot

log = logging.getLogger(__name__)


def _get_handler(categoria: str):
    """Wrapper para permitir mock em testes."""
    import core.categorias as cats

    return cats.get_handler(categoria)


def _sync_cliente_db(session: Session, pub: ClientePublico) -> Cliente:
    cliente = session.scalar(select(Cliente).where(Cliente.slug == pub.slug))
    if cliente is None:
        cliente = Cliente(slug=pub.slug, nome=pub.nome, categoria=Categoria(pub.categoria))
        session.add(cliente)
    else:
        cliente.nome = pub.nome
        cliente.categoria = Categoria(pub.categoria)
    cliente.logo_url = pub.logo_url
    cliente.descricao_publica = pub.descricao_publica
    cliente.setor = pub.setor
    cliente.porte = pub.porte
    cliente.publicar_vitrine = pub.publicar_vitrine
    session.flush()
    return cliente


def processar_cliente(
    *,
    pub: ClientePublico,
    cliente_db_id: uuid.UUID,
    periodo_ref,
    periodo_comp,
    frequencia: Frequencia,
    session_factory: Callable[[], Session] = SessionLocal,
) -> bool:
    try:
        handler = _get_handler(pub.categoria)
        dados = handler.coletar_dados(pub.cliente_core, periodo_ref, periodo_comp)

        payload = map_handler_dados(dados)

        session = session_factory()
        own_session = session_factory is SessionLocal
        try:
            upsert_snapshot(
                session,
                cliente_id=cliente_db_id,
                periodo_inicio=periodo_ref.inicio,
                periodo_fim=periodo_ref.fim,
                frequencia=frequencia,
                dados=payload,
            )
            session.commit()
        finally:
            if own_session:
                session.close()

        log.info("etl_snapshot_gravado", extra={"cliente": pub.nome})
        return True
    except Exception:
        log.exception("etl_falhou", extra={"cliente": pub.nome})
        return False


def run_etl(
    today: date | None = None,
    frequencia_str: str | None = None,
    slugs: set[str] | None = None,
    incluir_privados: bool = False,
) -> dict:
    """Roda o ETL completo.

    - slugs=None + incluir_privados=False: clientes da planilha com publicar_vitrine=True (default).
    - slugs={"loja-fashion"}: roda apenas esses (independente da flag), útil para testes.
    - incluir_privados=True: ignora publicar_vitrine, roda para todos os clientes da planilha.
    """
    from .cliente_publico import slugify
    settings = get_settings()
    today = today or date.today()
    frequencia_str = frequencia_str or settings.etl_periodo_granularidade
    frequencia = Frequencia(frequencia_str)

    from core.periodo import periodo_referencia
    from .sync_planilha import fetch_clientes_tolerante

    # Suprime escrita na Planilha Central durante o ETL da vitrine.
    # O auto-report original chama _update_status_cell para marcar status como
    # "PROCESSANDO", "ERRO API META", etc. Para a vitrine, não queremos tocar
    # na planilha do usuário — só ler e gravar no nosso Postgres.
    import core.leitura_central as _lc
    _original_update = _lc._update_status_cell
    _lc._update_status_cell = lambda *a, **kw: None
    try:
        # Também tenta interceptar batch updates no _parse_rows
        pass
    finally:
        pass

    try:
        with advisory_lock(engine, "etl:vitrine:run", blocking=False):
            todos_core = fetch_clientes_tolerante()
            pubs = [ClientePublico.from_cliente(c) for c in todos_core]
            if slugs:
                pubs = [p for p in pubs if slugify(p.nome) in slugs]
            elif not incluir_privados:
                pubs = [p for p in pubs if p.publicar_vitrine]
            log.info("etl_iniciado", extra={"n_clientes": len(pubs), "frequencia": frequencia_str})

            periodo_ref = periodo_referencia(today=today, frequencia=frequencia_str)
            periodo_comp = periodo_referencia(today=periodo_ref.inicio, frequencia=frequencia_str)

            ids: dict[str, uuid.UUID] = {}
            with SessionLocal() as session:
                for p in pubs:
                    cdb = _sync_cliente_db(session, p)
                    ids[p.slug] = cdb.id
                session.commit()

            ok = 0
            fail = 0
            with ThreadPoolExecutor(max_workers=settings.etl_threads) as pool:
                futures = {
                    pool.submit(
                        processar_cliente,
                        pub=p,
                        cliente_db_id=ids[p.slug],
                        periodo_ref=periodo_ref,
                        periodo_comp=periodo_comp,
                        frequencia=frequencia,
                    ): p
                    for p in pubs
                }
                for f in as_completed(futures):
                    if f.result():
                        ok += 1
                    else:
                        fail += 1

            resumo = {"ok": ok, "fail": fail, "total": len(pubs)}
            log.info("etl_finalizado", extra=resumo)
            alert(resumo)
            return resumo
    except LockTaken:
        log.warning("etl_skip_lock_ocupado")
        return {"skipped": True}
    finally:
        # restaura escrita na planilha (o auto-report normal continua funcionando)
        _lc._update_status_cell = _original_update


def backfill_clientes_meses(
    mes_inicio: str,
    mes_fim: str,
    slug: str | None = None,
    progress_callback: "Callable[[int, int, int], None] | None" = None,
) -> dict:
    """Roda ETL para um intervalo de meses usando slugs do banco de dados.

    Para cada mês do intervalo, chama run_etl com today=1º dia do mês seguinte,
    o que faz periodo_referencia retornar o mês-alvo como período de referência.

    Args:
        mes_inicio: "YYYY-MM" (inclusive)
        mes_fim:    "YYYY-MM" (inclusive)
        slug:       se fornecido, processa apenas esse cliente
        progress_callback: chamado após cada mês com (concluidos, total, erros)

    Returns:
        {"meses_processados": int, "meses_com_erro": list[str], "ok": int, "fail": int}
    """
    import time

    def _next_month(ano: int, mes: int) -> tuple[int, int]:
        return (ano + 1, 1) if mes == 12 else (ano, mes + 1)

    ano_i, mes_i = int(mes_inicio[:4]), int(mes_inicio[5:])
    ano_f, mes_f = int(mes_fim[:4]), int(mes_fim[5:])

    # Validar que mes_inicio <= mes_fim
    if (ano_i, mes_i) > (ano_f, mes_f):
        raise ValueError(f"mes_inicio ({mes_inicio}) deve ser <= mes_fim ({mes_fim})")

    meses: list[tuple[int, int]] = []
    ano, mes = ano_i, mes_i
    while (ano, mes) <= (ano_f, mes_f):
        meses.append((ano, mes))
        ano, mes = _next_month(ano, mes)

    # Slugs a processar — do banco, não da planilha
    if slug:
        slugs: set[str] = {slug}
    else:
        with SessionLocal() as session:
            slugs = set(session.execute(select(Cliente.slug)).scalars().all())

    resultados: dict = {
        "meses_processados": 0,
        "meses_com_erro": [],
        "ok": 0,
        "fail": 0,
    }

    for i, (ano_m, mes_m) in enumerate(meses):
        ano_next, mes_next = _next_month(ano_m, mes_m)
        today_ref = date(ano_next, mes_next, 1)
        mes_str = f"{ano_m:04d}-{mes_m:02d}"

        try:
            result = run_etl(today=today_ref, slugs=slugs, incluir_privados=True)
            if result.get("skipped"):
                # Lock ocupado — aguarda e retenta uma vez
                time.sleep(5)
                result = run_etl(today=today_ref, slugs=slugs, incluir_privados=True)
            if result.get("skipped"):
                # Ainda está skipped após retry — registrar como erro
                log.warning("backfill_mes_lock_persistente", extra={"mes": mes_str})
                resultados["meses_com_erro"].append(mes_str)
            else:
                resultados["ok"] += result.get("ok", 0)
                resultados["fail"] += result.get("fail", 0)
        except Exception:
            log.exception("backfill_mes_falhou", extra={"mes": mes_str})
            resultados["meses_com_erro"].append(mes_str)
            resultados["fail"] += 1

        resultados["meses_processados"] += 1
        if progress_callback:
            progress_callback(
                i + 1,
                len(meses),
                len(resultados["meses_com_erro"]),
            )

    return resultados
