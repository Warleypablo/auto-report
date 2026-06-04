from datetime import date

from services.clickup_match import (
    normalizar,
    score,
    classificar,
    melhores_candidatos,
    responsavel_performance,
)


# ── normalizar ──────────────────────────────────────────────────────────
def test_normalizar_remove_acento_caixa_e_sufixo():
    assert normalizar("Tuá Cosméticos LTDA") == "tua cosmeticos"
    assert normalizar("  Loja   X  ") == "loja x"


# ── score: matches fortes devem passar de 0.90 ──────────────────────────
import pytest

MATCHES_FORTES = [
    ("Noway Drinks", "Noway Drink"),
    ("Zacca", "Zacca Brasil"),
    ("Lahza Foods", "Lahza"),
    ("AtriumVix", "Atrium"),
    ("Medicinal da Web", "Medicinal na Web"),
    ("Kaowz Facas", "Kaowz"),
    ("Lavira", "Lavira"),
]

@pytest.mark.parametrize("a,b", MATCHES_FORTES)
def test_score_match_forte_acima_de_090(a, b):
    assert score(a, b) >= 0.90, f"{a} ~ {b} = {score(a, b):.2f}"


# ── score: lixo NUNCA pode chegar a 0.90 (anti-falso-positivo) ──────────
LIXO = [
    ("Fleur Brasil", "UR"),
    ("Nomã", "Bueno Mate"),
    ("Maves StreetWear Ecommerce", "Areco"),
    ("Haux", "Audax"),
    ("Mineral Pro", "MEATPRO"),
    ("Sim! Cerveja", "MS Creative"),
    ("Cosmobeauty", "Beautyin"),
]

@pytest.mark.parametrize("a,b", LIXO)
def test_score_lixo_abaixo_de_090(a, b):
    assert score(a, b) < 0.90, f"{a} ~ {b} = {score(a, b):.2f}"


# ── classificar ─────────────────────────────────────────────────────────
def test_classificar_auto_quando_alto_e_unico():
    assert classificar([(0.95, "t1", "Noway Drink")]) == "auto"

def test_classificar_sugestao_quando_ambiguo():
    # dois candidatos altos e próximos -> margem insuficiente
    assert classificar([(0.95, "t1", "A"), (0.93, "t2", "B")]) == "sugestao"

def test_classificar_sugestao_quando_medio():
    assert classificar([(0.80, "t1", "A")]) == "sugestao"

def test_classificar_sem_candidato_quando_baixo():
    assert classificar([(0.40, "t1", "A")]) == "sem_candidato"
    assert classificar([]) == "sem_candidato"


# ── melhores_candidatos ─────────────────────────────────────────────────
def test_melhores_candidatos_ordena_por_score_desc():
    cup = [
        {"task_id": "t1", "nome": "Atrium"},
        {"task_id": "t2", "nome": "Padaria do Zé"},
        {"task_id": "t3", "nome": "Atrium Holding"},
    ]
    res = melhores_candidatos("AtriumVix", cup, k=2)
    assert len(res) == 2
    assert res[0][0] >= res[1][0]
    assert res[0][1] in {"t1", "t3"}


# ── responsavel_performance: vigência ───────────────────────────────────
def test_responsavel_prefere_contrato_ativo_sobre_cancelado():
    contratos = [
        {"servico": "Gestão de Performance", "status": "cancelado/inativo",
         "responsavel": "Antigo", "data_inicio": date(2026, 5, 1)},
        {"servico": "Gestão de Performance", "status": "ativo",
         "responsavel": "Atual", "data_inicio": date(2026, 1, 1)},
    ]
    assert responsavel_performance(contratos) == "Atual"

def test_responsavel_mais_recente_entre_vigentes():
    contratos = [
        {"servico": "Gestão de Performance", "status": "ativo",
         "responsavel": "Velho", "data_inicio": date(2025, 1, 1)},
        {"servico": "Gestão de Performance", "status": "ativo",
         "responsavel": "Novo", "data_inicio": date(2026, 1, 1)},
    ]
    assert responsavel_performance(contratos) == "Novo"

def test_responsavel_ignora_servico_nao_performance():
    contratos = [
        {"servico": "Consultoria", "status": "ativo",
         "responsavel": "X", "data_inicio": date(2026, 1, 1)},
    ]
    assert responsavel_performance(contratos) is None

def test_responsavel_ignora_responsavel_vazio():
    contratos = [
        {"servico": "Gestão de Performance", "status": "ativo",
         "responsavel": "   ", "data_inicio": date(2026, 1, 1)},
    ]
    assert responsavel_performance(contratos) is None


def test_responsavel_ignora_contrato_cancelado():
    # Conta encerrada: o único contrato de Performance está cancelado → não há
    # gestor de performance vigente (não herdar o responsável do contrato morto).
    contratos = [
        {"servico": "Performance", "status": "cancelado/inativo",
         "responsavel": "Gestor que Saiu", "data_inicio": date(2025, 1, 1)},
    ]
    assert responsavel_performance(contratos) is None
