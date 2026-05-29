import csv
import io

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Categoria, Cliente
from models.base import Base
from scripts.audit_ids import auditar_ids, escrever_csv, formatar_tabela

TEST_DB_URL = "postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test"


@pytest.fixture
def TS():
    engine = create_engine(TEST_DB_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _cli(s, slug, *, meta=None, google=None, ativo=True):
    c = Cliente(
        slug=slug,
        nome=slug,
        categoria=Categoria.ECOMMERCE,
        id_meta_ads=meta,
        id_google_ads=google,
        ativo=ativo,
    )
    s.add(c)
    s.commit()
    return c


def test_auditar_ids_lista_apenas_ativos_com_id_faltante(TS):
    with TS() as s:
        _cli(s, "completo", meta="m1", google="g1")          # nao aparece
        _cli(s, "sem-meta", meta=None, google="g2")          # falta meta
        _cli(s, "sem-google", meta="m3", google=None)        # falta google
        _cli(s, "sem-ambos", meta=None, google=None)         # falta os dois
        _cli(s, "inativo", meta=None, google=None, ativo=False)  # ignorado (inativo)

        rows = auditar_ids(s)

    by_slug = {r["slug"]: r for r in rows}
    assert set(by_slug) == {"sem-meta", "sem-google", "sem-ambos"}
    assert by_slug["sem-meta"]["falta_meta"] is True
    assert by_slug["sem-meta"]["falta_google"] is False
    assert by_slug["sem-google"]["falta_meta"] is False
    assert by_slug["sem-google"]["falta_google"] is True
    assert by_slug["sem-ambos"]["falta_meta"] is True
    assert by_slug["sem-ambos"]["falta_google"] is True


def test_auditar_ids_ordena_por_slug(TS):
    with TS() as s:
        _cli(s, "zeta", meta=None)
        _cli(s, "alfa", meta=None)
        rows = auditar_ids(s)
    assert [r["slug"] for r in rows] == ["alfa", "zeta"]


def test_formatar_tabela_inclui_header_e_slugs():
    rows = [
        {"slug": "sem-meta", "nome": "Sem Meta", "falta_meta": True, "falta_google": False},
    ]
    out = formatar_tabela(rows)
    assert "slug" in out
    assert "sem-meta" in out
    assert "Sem Meta" in out


def test_escrever_csv_gera_cabecalho_e_linhas():
    rows = [
        {"slug": "sem-ambos", "nome": "Sem Ambos", "falta_meta": True, "falta_google": True},
    ]
    buf = io.StringIO()
    escrever_csv(rows, buf)
    buf.seek(0)
    parsed = list(csv.reader(buf))
    assert parsed[0] == ["slug", "nome", "falta_meta", "falta_google"]
    assert parsed[1] == ["sem-ambos", "Sem Ambos", "True", "True"]
