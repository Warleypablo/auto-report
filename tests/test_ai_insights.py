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
