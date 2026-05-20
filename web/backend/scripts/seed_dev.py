"""Popula DB com 10 clientes fictícios variados para a vitrine."""
from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import SessionLocal  # noqa: E402
from models import Categoria, Cliente, Snapshot  # noqa: E402
from models.snapshot import Frequencia  # noqa: E402


# (slug, nome, setor, porte, categoria, descricao, destaque,
#  fat_base, inv_base, roas_base, cpa_base, leads_base, vendas_base,
#  fat_growth_pct, roas_growth_pct, meta_share, google_share)
CLIENTES_DATA = [
    ("loja-fashion", "Loja Fashion BR", "Moda", "Médio", Categoria.ECOMMERCE,
     "E-commerce de moda feminina que escalou de R$ 80k/mês para R$ 1,2M em 12 meses, segmentando criativos por estilo de vida.",
     True, 1_200_000, 180_000, 6.7, 92.0, 0, 480, 23.5, 4.8, 0.42, 0.58),

    ("dental-care", "Dental Care+", "Saúde", "Pequeno", Categoria.LEAD_COM_SITE,
     "Rede de clínicas odontológicas que reduziu CPL em 61% após reestruturar funil de busca e remarketing.",
     False, 0, 35_000, 0, 71.0, 492, 0, 0, 0, 0.55, 0.45),

    ("atlas-cosmeticos", "Atlas Cosméticos", "Beleza", "Grande", Categoria.ECOMMERCE,
     "Marca premium de skincare que dobrou de tamanho em 8 meses combinando Meta com Google Shopping de alta intenção.",
     True, 3_840_000, 520_000, 7.4, 138.0, 0, 1_240, 18.2, 6.1, 0.51, 0.49),

    ("verdana-suplementos", "Verdana Suplementos", "Saúde", "Médio", Categoria.ECOMMERCE,
     "Marca de suplementos vegetais que atingiu ROAS 9,2x focando em criativos UGC e nichos de wellness.",
     False, 980_000, 105_000, 9.2, 84.0, 0, 390, 31.8, 12.4, 0.62, 0.38),

    ("northwave-fitness", "Northwave Fitness", "Lifestyle", "Médio", Categoria.LEAD_COM_SITE,
     "Rede de academias boutique que triplicou o pipeline de leads qualificados com landing pages segmentadas por bairro.",
     True, 0, 88_000, 0, 47.0, 1_870, 0, 0, 0, 0.61, 0.39),

    ("caldeira-construtora", "Caldeira Construtora", "Imobiliário", "Grande", Categoria.LEAD_COM_SITE,
     "Construtora de alto padrão que reduziu CPL em 38% e aumentou em 2,4× o volume de leads enquanto subia o ticket médio.",
     False, 0, 240_000, 0, 312.0, 770, 0, 0, 0, 0.38, 0.62),

    ("tribu-surf", "Tribu Surf", "Esporte", "Pequeno", Categoria.ECOMMERCE,
     "Marca de pranchas e acessórios de surf que cresceu 142% no faturamento orgânico após reestruturação do feed Shopping.",
     False, 285_000, 38_000, 7.5, 79.0, 0, 142, 27.4, 9.1, 0.55, 0.45),

    ("pelagia-pet", "Pelagia Pet", "Pet", "Grande", Categoria.ECOMMERCE,
     "Loja de produtos premium para pets que escalou para R$ 2,8M/mês mantendo ROAS acima de 8x com automação de catálogo.",
     True, 2_780_000, 320_000, 8.7, 96.0, 0, 920, 14.6, 5.2, 0.48, 0.52),

    ("estudio-onix", "Estúdio Ônix", "Beleza", "Pequeno", Categoria.LEAD_SEM_SITE,
     "Salão de beleza de alto padrão que lota agenda exclusivamente via Meta Ads, sem website próprio.",
     False, 0, 18_000, 0, 38.0, 480, 0, 0, 0, 1.0, 0.0),

    ("plataforma-aurora", "Plataforma Aurora", "Educação", "Médio", Categoria.LEAD_COM_SITE,
     "EdTech de cursos profissionalizantes que reduziu CAC em 44% após implementar funil de webinar e nutrição via Meta.",
     False, 0, 145_000, 0, 187.0, 920, 0, 0, 0, 0.71, 0.29),
]


MESES = 6


def _snapshots_para(cliente, base_data: tuple) -> list[Snapshot]:
    (_, _, _, _, categoria, _, _,
     fat_base, inv_base, roas_base, cpa_base, leads_base, vendas_base,
     fat_growth, roas_growth, meta_share, google_share) = base_data

    snaps: list[Snapshot] = []
    # mês mais recente fechado: 2026-04 (hoje é 2026-05-20)
    meses_ref = [
        (date(2025, 11, 1), date(2025, 11, 30)),
        (date(2025, 12, 1), date(2025, 12, 31)),
        (date(2026, 1, 1), date(2026, 1, 31)),
        (date(2026, 2, 1), date(2026, 2, 28)),
        (date(2026, 3, 1), date(2026, 3, 31)),
        (date(2026, 4, 1), date(2026, 4, 30)),
    ]
    # cresce do mais antigo para o mais novo (geometricamente)
    growth_step = (1 + fat_growth / 100.0) ** (1 / max(MESES - 1, 1)) if fat_base else 1

    for i, (ini, fim) in enumerate(meses_ref):
        # i=0 (mais antigo) … i=MESES-1 (mais novo)
        fat = Decimal(str(round(fat_base / (growth_step ** (MESES - 1 - i)), 2))) if fat_base else None
        inv = Decimal(str(round(inv_base * (0.85 + 0.05 * i), 2)))
        roas = Decimal(str(round(roas_base * (0.88 + 0.025 * i), 4))) if roas_base else None
        cpa = Decimal(str(round(cpa_base * (1.6 - 0.10 * i), 2))) if cpa_base else None
        leads = int(leads_base * (0.55 + 0.075 * i)) if leads_base else None
        vendas = int(vendas_base * (0.55 + 0.075 * i)) if vendas_base else None

        fat_var = Decimal(str(round(fat_growth / MESES, 2))) if fat_growth else None
        roas_var = Decimal(str(round(roas_growth / MESES, 2))) if roas_growth else None

        fat_f = float(fat) if fat else 0
        inv_f = float(inv)
        roas_f = float(roas) if roas else 0
        cpa_f = float(cpa) if cpa else 0

        det = {}
        if meta_share > 0:
            det["meta"] = {
                "faturamento": round(fat_f * meta_share, 2),
                "investimento": round(inv_f * meta_share, 2),
                "roas": round(roas_f * 0.95, 2),
                "cpa": round(cpa_f * 1.05, 2),
            }
        if google_share > 0:
            det["google"] = {
                "faturamento": round(fat_f * google_share, 2),
                "investimento": round(inv_f * google_share, 2),
                "roas": round(roas_f * 1.05, 2),
                "cpa": round(cpa_f * 0.95, 2),
            }
        if categoria == Categoria.ECOMMERCE:
            det["ga4"] = {
                "sessoes": int(50_000 * (0.6 + 0.07 * i)),
                "sessoes_engajadas": int(38_000 * (0.6 + 0.07 * i)),
                "taxa_engajamento": 76,
            }

        snaps.append(Snapshot(
            cliente_id=cliente.id,
            periodo_inicio=ini,
            periodo_fim=fim,
            frequencia=Frequencia.MENSAL,
            faturamento=fat,
            investimento=inv,
            roas=roas,
            cpa=cpa,
            leads=leads,
            vendas=vendas,
            faturamento_var_pct=fat_var,
            roas_var_pct=roas_var,
            metricas_detalhadas=det,
            raw_dados={},
        ))
    return snaps


def main() -> None:
    with SessionLocal() as session:
        for data in CLIENTES_DATA:
            slug, nome, setor, porte, categoria, descricao, destaque = data[:7]
            cliente = session.query(Cliente).filter_by(slug=slug).first()
            if cliente:
                # limpa snapshots antigos para repopular
                session.query(Snapshot).filter(Snapshot.cliente_id == cliente.id).delete()
                cliente.nome = nome
                cliente.setor = setor
                cliente.porte = porte
                cliente.categoria = categoria
                cliente.descricao_publica = descricao
                cliente.destaque = destaque
                cliente.publicar_vitrine = True
                cliente.logo_url = f"/logos/{slug}.svg"
            else:
                cliente = Cliente(
                    slug=slug,
                    nome=nome,
                    setor=setor,
                    porte=porte,
                    categoria=categoria,
                    descricao_publica=descricao,
                    destaque=destaque,
                    publicar_vitrine=True,
                    logo_url=f"/logos/{slug}.svg",
                )
                session.add(cliente)
                session.flush()

            for snap in _snapshots_para(cliente, data):
                session.add(snap)
        session.commit()
        print(f"Seeded {len(CLIENTES_DATA)} clientes com {len(CLIENTES_DATA) * MESES} snapshots")


if __name__ == "__main__":
    main()
