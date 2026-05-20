"""Popula DB com clientes e snapshots fictícios para dev local."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import SessionLocal  # noqa: E402
from models import Categoria, Cliente, Snapshot  # noqa: E402
from models.snapshot import Frequencia  # noqa: E402


CLIENTES = [
    dict(
        slug="loja-fashion",
        nome="Loja Fashion BR",
        logo_url="/logos/loja-fashion.svg",
        categoria=Categoria.ECOMMERCE,
        setor="Moda",
        porte="Médio",
        descricao_publica="E-commerce de moda feminina que cresceu 230% em 12 meses.",
        publicar_vitrine=True,
        destaque=True,
    ),
    dict(
        slug="dental-care",
        nome="Dental Care+",
        logo_url="/logos/dental-care.svg",
        categoria=Categoria.LEAD_COM_SITE,
        setor="Saúde",
        porte="Pequeno",
        descricao_publica="Clínica odontológica que reduziu CPL em 60%.",
        publicar_vitrine=True,
        destaque=False,
    ),
]


def main() -> None:
    with SessionLocal() as session:
        for data in CLIENTES:
            existing = session.query(Cliente).filter_by(slug=data["slug"]).first()
            if existing:
                print(f"Cliente {data['slug']} já existe, pulando")
                continue
            cliente = Cliente(**data)
            session.add(cliente)
            session.flush()

            hoje = date.today()
            for i in range(6):
                meses_atras = i
                ref = hoje.replace(day=1) - timedelta(days=1)
                for _ in range(meses_atras):
                    ref = ref.replace(day=1) - timedelta(days=1)
                periodo_fim = ref
                periodo_inicio = ref.replace(day=1)
                snap = Snapshot(
                    cliente_id=cliente.id,
                    periodo_inicio=periodo_inicio,
                    periodo_fim=periodo_fim,
                    frequencia=Frequencia.MENSAL,
                    faturamento=Decimal("100000") + Decimal(i) * Decimal("20000"),
                    investimento=Decimal("15000"),
                    roas=Decimal("6.5") + Decimal(i) * Decimal("0.3"),
                    cpa=Decimal("85.50"),
                    leads=200 + 20 * i,
                    vendas=50 + 5 * i,
                    faturamento_var_pct=Decimal("12.5"),
                    roas_var_pct=Decimal("4.8"),
                    metricas_detalhadas={
                        "meta": {"roas": 7.0, "faturamento": 40000},
                        "google": {"roas": 8.2, "faturamento": 50000},
                    },
                    raw_dados={},
                )
                session.add(snap)
        session.commit()
        print(f"Seeded {len(CLIENTES)} clientes")


if __name__ == "__main__":
    main()
