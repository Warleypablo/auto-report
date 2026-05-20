from __future__ import annotations

from models import Cliente, Snapshot
from schemas import CaseDetail, CaseListItem, PontoEvolucao


def build_case_list_item(cliente: Cliente, snapshot: Snapshot) -> CaseListItem:
    return CaseListItem(
        slug=cliente.slug,
        nome=cliente.nome,
        logo_url=cliente.logo_url,
        categoria=cliente.categoria.value,
        setor=cliente.setor,
        porte=cliente.porte,
        descricao_publica=cliente.descricao_publica,
        destaque=cliente.destaque,
        periodo_inicio=snapshot.periodo_inicio,
        periodo_fim=snapshot.periodo_fim,
        faturamento=snapshot.faturamento,
        investimento=snapshot.investimento,
        roas=snapshot.roas,
        cpa=snapshot.cpa,
        leads=snapshot.leads,
        vendas=snapshot.vendas,
        faturamento_var_pct=snapshot.faturamento_var_pct,
        roas_var_pct=snapshot.roas_var_pct,
    )


def build_case_detail(
    cliente: Cliente,
    snapshot_atual: Snapshot,
    historico: list[Snapshot],
) -> CaseDetail:
    base = build_case_list_item(cliente, snapshot_atual).model_dump()
    return CaseDetail(
        **base,
        metricas_detalhadas=snapshot_atual.metricas_detalhadas or {},
        evolucao=[
            PontoEvolucao(
                periodo_inicio=s.periodo_inicio,
                periodo_fim=s.periodo_fim,
                faturamento=s.faturamento,
                investimento=s.investimento,
                roas=s.roas,
            )
            for s in sorted(historico, key=lambda x: x.periodo_fim)
        ],
        data_coleta=snapshot_atual.data_coleta,
    )
