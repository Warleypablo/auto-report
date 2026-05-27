import pytest


def test_insight_model_importavel():
    from models.insight import Insight
    assert Insight.__tablename__ == "insights"


# Fixtures
def _bd_brand():
    return {
        "google_ads": [
            {"nome": "[TP] - [Inst] - [09/10]", "roas": 577.57, "investimento": 74.75,
             "faturamento": 43175.90, "conversoes": 37.49, "cpa": 1.99, "impressoes": 4323},
            {"nome": "[TP] - [Shop] - [26/08]", "roas": 32.80, "investimento": 7919.96,
             "faturamento": 259813.29, "conversoes": 199.88, "cpa": 39.62, "impressoes": 828660},
        ],
        "meta_ads": [],
    }

# detectar_roas_brand_inflado
def test_roas_brand_inflado_dispara():
    from services.inteligencia import detectar_roas_brand_inflado
    sinal = detectar_roas_brand_inflado(_bd_brand())
    assert sinal is not None
    assert sinal["tipo"] == "roas_brand_inflado"
    assert sinal["severidade"] == "atencao"
    assert sinal["contexto"]["roas_sem_brand"] == pytest.approx(32.80, rel=0.02)

def test_roas_brand_inflado_nao_dispara_sem_brand():
    from services.inteligencia import detectar_roas_brand_inflado
    bd = {"google_ads": [{"nome": "[TP] - [Shop] - [26/08]", "roas": 32.80, "investimento": 7919.96, "faturamento": 259813.29, "conversoes": 199.88, "cpa": 39.62, "impressoes": 828660}], "meta_ads": []}
    assert detectar_roas_brand_inflado(bd) is None

def test_roas_brand_inflado_nao_dispara_roas_baixo():
    from services.inteligencia import detectar_roas_brand_inflado
    bd = {"google_ads": [{"nome": "[TP] - [Brand] - [01/01]", "roas": 8.0, "investimento": 500.0, "faturamento": 4000.0, "conversoes": 10, "cpa": 50.0, "impressoes": 1000}], "meta_ads": []}
    assert detectar_roas_brand_inflado(bd) is None

# detectar_roas_queda
def test_roas_queda_dispara():
    from decimal import Decimal
    from services.inteligencia import detectar_roas_queda
    class FakeSnap:
        roas = None
    atual = FakeSnap(); atual.roas = Decimal("5.7")
    anterior = FakeSnap(); anterior.roas = Decimal("8.4")
    sinal = detectar_roas_queda(atual, anterior)
    assert sinal is not None
    assert sinal["tipo"] == "roas_queda"
    assert sinal["severidade"] == "critico"

def test_roas_queda_nao_dispara_queda_pequena():
    from decimal import Decimal
    from services.inteligencia import detectar_roas_queda
    class FakeSnap:
        roas = None
    atual = FakeSnap(); atual.roas = Decimal("8.0")
    anterior = FakeSnap(); anterior.roas = Decimal("8.5")
    assert detectar_roas_queda(atual, anterior) is None

def test_roas_queda_nao_dispara_sem_anterior():
    from decimal import Decimal
    from services.inteligencia import detectar_roas_queda
    class FakeSnap:
        roas = None
    atual = FakeSnap(); atual.roas = Decimal("5.0")
    assert detectar_roas_queda(atual, None) is None

# detectar_roas_abaixo_limiar
def test_roas_abaixo_limiar_dispara():
    from decimal import Decimal
    from services.inteligencia import detectar_roas_abaixo_limiar
    class FakeSnap:
        roas = None
    snap = FakeSnap(); snap.roas = Decimal("1.2")
    assert detectar_roas_abaixo_limiar(snap) is not None

def test_roas_abaixo_limiar_nao_dispara_acima():
    from decimal import Decimal
    from services.inteligencia import detectar_roas_abaixo_limiar
    class FakeSnap:
        roas = None
    snap = FakeSnap(); snap.roas = Decimal("2.5")
    assert detectar_roas_abaixo_limiar(snap) is None

# detectar_faturamento_queda
def test_faturamento_queda_dispara():
    from decimal import Decimal
    from services.inteligencia import detectar_faturamento_queda
    class FakeSnap:
        faturamento = None
    atual = FakeSnap(); atual.faturamento = Decimal("60000.0")
    anterior = FakeSnap(); anterior.faturamento = Decimal("100000.0")
    sinal = detectar_faturamento_queda(atual, anterior)
    assert sinal is not None
    assert sinal["tipo"] == "faturamento_queda"
    assert sinal["severidade"] == "critico"

def test_faturamento_queda_nao_dispara_queda_pequena():
    from decimal import Decimal
    from services.inteligencia import detectar_faturamento_queda
    class FakeSnap:
        faturamento = None
    atual = FakeSnap(); atual.faturamento = Decimal("90000.0")
    anterior = FakeSnap(); anterior.faturamento = Decimal("100000.0")
    assert detectar_faturamento_queda(atual, anterior) is None

def test_faturamento_queda_nao_dispara_sem_anterior():
    from decimal import Decimal
    from services.inteligencia import detectar_faturamento_queda
    class FakeSnap:
        faturamento = None
    atual = FakeSnap(); atual.faturamento = Decimal("60000.0")
    assert detectar_faturamento_queda(atual, None) is None

# detectar_investimento_parado
def test_investimento_parado_dispara_sem_snap():
    from services.inteligencia import detectar_investimento_parado
    assert detectar_investimento_parado(None) is not None

def test_investimento_parado_nao_dispara_com_investimento():
    from decimal import Decimal
    from services.inteligencia import detectar_investimento_parado
    class FakeSnap:
        investimento = Decimal("1000.0")
    assert detectar_investimento_parado(FakeSnap()) is None

# detectar_oportunidade_escala
def test_oportunidade_escala_dispara():
    from decimal import Decimal
    from services.inteligencia import detectar_oportunidade_escala
    class FakeSnap:
        roas = None
        investimento = None
    snap = FakeSnap(); snap.roas = Decimal("8.0"); snap.investimento = Decimal("1000.0")
    sinal = detectar_oportunidade_escala(snap, 10000.0)
    assert sinal is not None
    assert sinal["tipo"] == "oportunidade_escala"
    assert sinal["severidade"] == "oportunidade"

def test_oportunidade_escala_nao_dispara_roas_baixo():
    from decimal import Decimal
    from services.inteligencia import detectar_oportunidade_escala
    class FakeSnap:
        roas = None
        investimento = None
    snap = FakeSnap(); snap.roas = Decimal("3.0"); snap.investimento = Decimal("1000.0")
    assert detectar_oportunidade_escala(snap, 10000.0) is None

def test_oportunidade_escala_nao_dispara_investimento_alto():
    from decimal import Decimal
    from services.inteligencia import detectar_oportunidade_escala
    class FakeSnap:
        roas = None
        investimento = None
    snap = FakeSnap(); snap.roas = Decimal("8.0"); snap.investimento = Decimal("8000.0")
    assert detectar_oportunidade_escala(snap, 10000.0) is None

# rodar_detectores
def test_rodar_detectores_retorna_lista():
    from decimal import Decimal
    from services.inteligencia import rodar_detectores
    class FakeSnap:
        roas = Decimal("5.7")
        investimento = Decimal("7000.0")
        faturamento = Decimal("40000.0")
    sinais = rodar_detectores(
        snap_atual=FakeSnap(),
        snap_anterior=None,
        breakdown=_bd_brand(),
        media_investimento_carteira=5000.0,
    )
    assert isinstance(sinais, list)
    assert any(s["tipo"] == "roas_brand_inflado" for s in sinais)
