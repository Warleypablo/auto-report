from decimal import Decimal

import pytest

from etl.transform import map_handler_dados, parse_metric, parse_pt_br


class TestParsePtBr:
    def test_brl_simples(self):
        assert parse_pt_br("R$ 12,34") == Decimal("12.34")

    def test_brl_com_milhar(self):
        assert parse_pt_br("R$ 12.345,67") == Decimal("12345.67")

    def test_brl_milhoes(self):
        assert parse_pt_br("R$ 1.234.567,89") == Decimal("1234567.89")

    def test_percentual_positivo(self):
        assert parse_pt_br("+12,5%") == Decimal("12.5")

    def test_percentual_negativo(self):
        assert parse_pt_br("-3,7%") == Decimal("-3.7")

    def test_percentual_sem_sinal(self):
        assert parse_pt_br("12,5%") == Decimal("12.5")

    def test_multiplicador(self):
        assert parse_pt_br("8,5x") == Decimal("8.5")

    def test_multiplicador_inteiro(self):
        assert parse_pt_br("12x") == Decimal("12")

    def test_inteiro_com_milhar(self):
        assert parse_pt_br("1.234") == Decimal("1234")

    def test_inteiro_simples(self):
        assert parse_pt_br("567") == Decimal("567")

    def test_decimal_simples(self):
        assert parse_pt_br("12,34") == Decimal("12.34")

    def test_decimal_zero_a_um(self):
        assert parse_pt_br("0,5") == Decimal("0.5")

    @pytest.mark.parametrize("entrada", ["", "-", "N/A", "n/a", None])
    def test_vazio_vira_none(self, entrada):
        assert parse_pt_br(entrada) is None

    def test_ja_decimal_preserva(self):
        assert parse_pt_br(Decimal("12.5")) == Decimal("12.5")

    def test_ja_int_preserva(self):
        assert parse_pt_br(10) == Decimal("10")

    def test_ja_float_preserva(self):
        assert parse_pt_br(12.5) == Decimal("12.5")

    def test_string_invalida_levanta(self):
        with pytest.raises(ValueError):
            parse_pt_br("não-é-número")

    def test_whitespace_extremos(self):
        assert parse_pt_br("  R$ 12,34  ") == Decimal("12.34")


class TestParseMetric:
    def test_parse_metric_normal(self):
        assert parse_metric("fat_face", "R$ 100,00") == Decimal("100")

    def test_parse_metric_invalido_retorna_none(self, caplog):
        result = parse_metric("fat_face", "xyz")
        assert result is None


class TestMapHandlerDados:
    def test_mapeia_metricas_destaque(self):
        # Destaque usa os placeholders MENSAIS ({{fat_mes}}/{{inv_mes}}); o ROAS
        # de destaque é DERIVADO de fat/inv (o {{roas}} do handler é semanal e
        # fica 0 antes do fechamento — ver commit fa3545f).
        entrada = {
            "{{fat_mes}}": "R$ 100.000,00",
            "{{inv_mes}}": "R$ 15.000,00",
            "{{cpa}}": "R$ 85,50",
            "{{vendas}}": "50",
            "{{fat_face}}": "R$ 40.000,00",
            "{{roas_face}}": "5,5x",
        }
        resultado = map_handler_dados(entrada)
        assert resultado["faturamento"] == Decimal("100000")
        assert resultado["investimento"] == Decimal("15000")
        assert resultado["roas"] == Decimal("6.6667")  # 100000 / 15000, derivado
        assert resultado["cpa"] == Decimal("85.50")
        assert resultado["vendas"] == 50
        assert resultado["metricas_detalhadas"]["meta"]["faturamento"] == Decimal("40000")
        assert resultado["metricas_detalhadas"]["meta"]["roas"] == Decimal("5.5")

    def test_consolida_destaque_somando_fontes_quando_painel_ausente(self):
        # Sem {{fat_mes}}/{{inv_mes}}, o destaque cai no fallback que soma as
        # fontes Meta + Google (resgata clientes com painel mensal desatualizado).
        entrada = {
            "{{fat_face}}": "R$ 40.000,00",
            "{{inv_face}}": "R$ 5.000,00",
            "{{fat_goog}}": "R$ 10.000,00",
            "{{inv_goog}}": "R$ 2.000,00",
        }
        resultado = map_handler_dados(entrada)
        assert resultado["faturamento"] == Decimal("50000")  # 40000 + 10000
        assert resultado["investimento"] == Decimal("7000")  # 5000 + 2000
        assert resultado["roas"] == Decimal("7.1429")  # 50000 / 7000, derivado

    def test_ignora_chave_desconhecida(self):
        entrada = {"{{chave_inexistente}}": "valor qualquer"}
        resultado = map_handler_dados(entrada)
        assert resultado.get("faturamento") is None
        assert resultado["raw_dados"] == entrada

    def test_preserva_raw(self):
        entrada = {"{{fat_sem}}": "R$ 1,00"}
        resultado = map_handler_dados(entrada)
        assert resultado["raw_dados"] == entrada
