"""
core/ai_insights.py

Gera a narrativa executiva do report (3-5 parágrafos, PT-BR) via Claude.
Desacoplado: recebe a API key por parâmetro (fallback p/ env). O SDK anthropic
é importado de forma lazy dentro de _chamar_claude — a chamada fica isolada e
mockável nos testes (sem precisar do SDK instalado).
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

_MODELO = "claude-sonnet-4-6"
_MIN_CHARS = 400
_MAX_CHARS = 2000

# Canais e as chaves de cada um (formato {{...}} cru, como vem do handler).
# (rótulo, [(label_metrica, chave_valor, chave_variacao_ou_None), ...])
_CANAIS = [
    ("Meta Ads", [
        ("faturamento", "{{fat_face}}", "{{var_fat_face}}"),
        ("ROAS", "{{roas_face}}", "{{var_roas_face}}"),
        ("investimento", "{{inv_face}}", "{{var_inv_face}}"),
        ("vendas", "{{vendas_face}}", "{{var_vendas_face}}"),
        ("CPA", "{{cpa_face}}", "{{var_cpa_face}}"),
    ]),
    ("Google Ads", [
        ("faturamento", "{{fat_goog}}", "{{var_fat_goog}}"),
        ("ROAS", "{{roas_goog}}", "{{var_roas_goog}}"),
        ("investimento", "{{inv_goog}}", "{{var_inv_goog}}"),
    ]),
    ("GA4", [
        ("sessões", "{{ses_ga}}", "{{var_ses_ga}}"),
        ("sessões (lead)", "{{ses}}", "{{var_ses}}"),
    ]),
    ("Painel de Negócio", [
        ("faturamento", "{{fat_sem}}", "{{var_fat_sem}}"),
        ("vendas", "{{vendas}}", "{{var_vendas}}"),
        ("leads", "{{lead_sem}}", "{{var_lead_sem}}"),
        ("CPL", "{{cpl}}", "{{var_cpl}}"),
        ("ticket médio", "{{tck_med}}", "{{var_tck_med}}"),
    ]),
]

_VAZIO = {"", "-", "—", "__NO_IMAGE__", None}


def _tem(v) -> bool:
    return v not in _VAZIO


def _validar_texto(texto) -> bool:
    """True se o texto tem tamanho razoável (não-vazio, entre _MIN e _MAX chars)."""
    if not isinstance(texto, str):
        return False
    n = len(texto.strip())
    return _MIN_CHARS <= n <= _MAX_CHARS


def _montar_resumo_factual(dados: dict, contexto: dict) -> str:
    """Monta um resumo estruturado e factual (só números reais) para a IA."""
    linhas = [
        f"Cliente: {contexto.get('cliente', '?')} ({contexto.get('categoria', '?')})",
        f"Período: {contexto.get('freq', '')} · {contexto.get('periodo', '')} (vs. período anterior)",
        "",
    ]
    for rotulo, metricas in _CANAIS:
        partes = []
        for label, chave_v, chave_var in metricas:
            v = dados.get(chave_v)
            if not _tem(v):
                continue
            var = dados.get(chave_var) if chave_var else None
            partes.append(f"{label} {v}" + (f" ({var})" if _tem(var) else ""))
        if partes:
            linhas.append(f"{rotulo}: " + " · ".join(partes))
        else:
            linhas.append(f"{rotulo}: sem dados no período")

    # Top criativos (Meta) — só os reais
    cria = []
    for i in range(1, 6):
        nome = dados.get(f"{{{{nome_adf{i}}}}}")
        if not _tem(nome):
            continue
        roas = dados.get(f"{{{{roas_adf{i}}}}}", "")
        conv = dados.get(f"{{{{conv_adf{i}}}}}", "")
        fat = dados.get(f"{{{{fat_adf{i}}}}}", "")
        cria.append(f'  {len(cria)+1}) "{nome}" — ROAS {roas} · {conv} conversões · {fat} faturamento')
    if cria:
        linhas.append("")
        linhas.append("TOP CRIATIVOS (Meta):")
        linhas.extend(cria)

    return "\n".join(linhas)


_SYSTEM_PROMPT = (
    "Você é um gestor de performance/tráfego sênior da Turbo Partners escrevendo "
    "a análise de um relatório para o dono do negócio (cliente).\n\n"
    "REGRAS OBRIGATÓRIAS:\n"
    "1. Use APENAS os números fornecidos no resumo. NUNCA invente, estime ou crie "
    "valores que não estão na lista. Se um dado não foi dado, não cite número.\n"
    "2. Não comente canais marcados como 'sem dados no período'.\n"
    "3. Escreva de 3 a 5 parágrafos curtos, em português do Brasil, fluido e claro, "
    "com tom de negócio — sem jargão técnico desnecessário e SEM bullet points.\n"
    "4. Destaque o que mais importa: o que cresceu ou caiu, o canal/criativo que "
    "puxou o resultado, e o contexto frente ao período anterior.\n"
    "5. Não escreva saudação, título nem assinatura. Apenas a análise."
)


def _chamar_claude(resumo: str, api_key: str, *, modelo: str = _MODELO, timeout: int = 15) -> str:
    """Chama a Claude e devolve o texto. Import lazy do SDK (isolado p/ testes)."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=modelo,
        max_tokens=1024,
        timeout=timeout,
        system=[{
            "type": "text",
            "text": _SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},  # cacheia o prompt fixo (lote barato)
        }],
        messages=[{"role": "user", "content": resumo}],
    )
    return resp.content[0].text


def gerar_analise(dados: dict, contexto: dict, api_key: str = "") -> str | None:
    """Narrativa executiva via Claude. Retorna o texto PT-BR ou None em falha/
    timeout/texto inválido (o report segue sem a página)."""
    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return None
    try:
        resumo = _montar_resumo_factual(dados, contexto)
        texto = _chamar_claude(resumo, key).strip()
        return texto if _validar_texto(texto) else None
    except Exception:
        log.exception("Falha ao gerar análise de IA (%s)", contexto.get("cliente"))
        return None
