"""
core/parallel_coleta.py

Roda coletores de canal (Painel, Meta, Google, GA4) em paralelo e mescla os
dicts de placeholders. Cada coletor cria seu próprio cliente de API e tem
timeout de HTTP, então são independentes/thread-safe. Os placeholders de cada
canal são disjuntos (e o sufixo "_comp" separa os períodos), então a ordem de
merge é irrelevante — o resultado é idêntico ao da coleta sequencial.

Timeout por tarefa: um canal travado não segura o report inteiro. shutdown sem
espera: não bloqueia o processo numa thread zumbi (que termina sozinha quando o
timeout de HTTP do coletor estoura).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable


def coletar_em_paralelo(
    tarefas: list[tuple[str, Callable[[], dict]]],
    *,
    timeout: int = 90,
    log=None,
) -> dict:
    dados: dict = {}
    if not tarefas:
        return dados
    ex = ThreadPoolExecutor(max_workers=len(tarefas))
    try:
        futs = {ex.submit(fn): nome for nome, fn in tarefas}
        for fut, nome in list(futs.items()):
            try:
                parcial = fut.result(timeout=timeout)
                if parcial:
                    dados.update(parcial)
            except Exception:
                if log is not None:
                    log.exception("Canal %s falhou/timeout na coleta paralela", nome)
    finally:
        ex.shutdown(wait=False)
    return dados
