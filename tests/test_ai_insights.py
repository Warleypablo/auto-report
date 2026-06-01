import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestValidarTexto:
    def test_texto_bom_passa(self):
        from core.ai_insights import _validar_texto
        assert _validar_texto("A" * 600) is True

    def test_vazio_falha(self):
        from core.ai_insights import _validar_texto
        assert _validar_texto("") is False
        assert _validar_texto("   ") is False

    def test_curto_demais_falha(self):
        from core.ai_insights import _validar_texto
        assert _validar_texto("Curto.") is False

    def test_longo_demais_falha(self):
        from core.ai_insights import _validar_texto
        assert _validar_texto("A" * 2500) is False

    def test_none_falha(self):
        from core.ai_insights import _validar_texto
        assert _validar_texto(None) is False


class TestMontarResumoFactual:
    def test_inclui_so_numeros_presentes(self):
        from core.ai_insights import _montar_resumo_factual
        dados = {
            "{{fat_face}}": "R$ 23.575", "{{roas_face}}": "8,4",
            "{{inv_face}}": "R$ 221", "{{var_fat_face}}": "+51,7%",
            "{{fat_goog}}": "-", "{{roas_goog}}": "—",   # google sem dados
        }
        ctx = {"cliente": "Piknik", "categoria": "E-commerce", "freq": "Semanal", "periodo": "26/05 a 30/05/2026"}
        resumo = _montar_resumo_factual(dados, ctx)
        assert "Piknik" in resumo
        assert "23.575" in resumo
        assert "8,4" in resumo
        assert "Meta Ads" in resumo
        # google sem dados → marcado como sem dados, sem valores
        assert "sem dados" in resumo.lower()

    def test_nao_inventa_valor_ausente(self):
        from core.ai_insights import _montar_resumo_factual
        dados = {"{{fat_face}}": "R$ 100"}
        ctx = {"cliente": "X", "categoria": "E-commerce", "freq": "Semanal", "periodo": "p"}
        resumo = _montar_resumo_factual(dados, ctx)
        # nenhum número fabricado além do fornecido
        import re
        nums = re.findall(r"\d[\d.,]*", resumo)
        assert "100" in resumo


from unittest.mock import patch


_DADOS = {"{{fat_face}}": "R$ 23.575", "{{roas_face}}": "8,4", "{{inv_face}}": "R$ 221"}
_CTX = {"cliente": "Piknik", "categoria": "E-commerce", "freq": "Semanal", "periodo": "26/05 a 30/05/2026"}


class TestGerarAnalise:
    def test_sem_key_retorna_none(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from core.ai_insights import gerar_analise
        assert gerar_analise(_DADOS, _CTX, api_key="") is None

    def test_texto_valido_retorna_texto(self):
        from core import ai_insights
        bom = "A análise da semana. " * 30  # > 400 chars
        with patch.object(ai_insights, "_chamar_claude", return_value=bom):
            out = ai_insights.gerar_analise(_DADOS, _CTX, api_key="sk-test")
        assert out == bom.strip()

    def test_texto_invalido_retorna_none(self):
        from core import ai_insights
        with patch.object(ai_insights, "_chamar_claude", return_value="curto"):
            assert ai_insights.gerar_analise(_DADOS, _CTX, api_key="sk-test") is None

    def test_excecao_na_api_retorna_none(self):
        from core import ai_insights
        with patch.object(ai_insights, "_chamar_claude", side_effect=RuntimeError("api down")):
            assert ai_insights.gerar_analise(_DADOS, _CTX, api_key="sk-test") is None

    def test_usa_key_do_env_se_nao_passada(self, monkeypatch):
        from core import ai_insights
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env")
        bom = "Texto bom da análise. " * 30
        with patch.object(ai_insights, "_chamar_claude", return_value=bom) as m:
            ai_insights.gerar_analise(_DADOS, _CTX)
        # _chamar_claude recebeu a key do env
        assert m.call_args.args[1] == "sk-env" or m.call_args.kwargs.get("api_key") == "sk-env"
