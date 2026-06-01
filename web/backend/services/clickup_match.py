from __future__ import annotations

import re
import unicodedata
from datetime import date as _date

from rapidfuzz import fuzz

# ── Normalização de nome (movida de api/gestor.py para reuso) ────────────
_SUFIXOS_JURIDICOS_RE = re.compile(
    r"\s+(ltda|me|mei|epp|eireli|s\.?a\.?|sa|inc\.?|corp\.?)\s*\.?\s*$",
    re.IGNORECASE,
)

# Tokens que não carregam identidade de marca — ignorados ao exigir
# "token significativo em comum" no guarda anti-falso-positivo.
_STOPWORDS = {
    "da", "de", "do", "das", "dos", "e",
    "ltda", "me", "mei", "epp", "eireli", "sa",
    "ecommerce", "ecomm", "whats", "whatsapp", "loja", "lojas",
}


def normalizar(s: str | None) -> str:
    """lower, sem acento, sem sufixo jurídico, sem pontuação, espaços colapsados."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = _SUFIXOS_JURIDICOS_RE.sub("", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokens_sig(s: str) -> set[str]:
    return {t for t in s.split() if len(t) >= 4 and t not in _STOPWORDS}


def _ha_token_em_comum(ta: set[str], tb: set[str]) -> bool:
    """Evidência de que os nomes falam da mesma marca: token igual, prefixo
    forte (nomes colados/abreviados) ou par de tokens muito similar."""
    for a in ta:
        for b in tb:
            if a == b:
                return True
            if len(a) >= 5 and len(b) >= 5 and (a.startswith(b) or b.startswith(a)):
                return True
            if fuzz.ratio(a, b) / 100.0 >= 0.85:
                return True
    return False


def score(nome_a: str, nome_b: str) -> float:
    """Similaridade 0..1 entre dois nomes, com guarda anti-falso-positivo.

    Retorna 0.0 quando não há token significativo em comum — bloqueia casos
    como 'Fleur Brasil'×'UR' e 'Nomã'×'Bueno Mate' que enganam métricas de
    substring.
    """
    a, b = normalizar(nome_a), normalizar(nome_b)
    if not a or not b:
        return 0.0
    ta, tb = _tokens_sig(a), _tokens_sig(b)
    if not ta or not tb or not _ha_token_em_comum(ta, tb):
        return 0.0

    base = max(fuzz.token_set_ratio(a, b), fuzz.token_sort_ratio(a, b)) / 100.0

    # Risco residual conhecido: um token líder curto e GENÉRICO ("Bella" em
    # "Bella Vista") é estruturalmente igual a um distintivo ("Zacca" em
    # "Zacca Brasil"), então um nome de 1 palavra genérico pode pontuar alto.
    # Não há separação estrutural; a defesa é a revisão humana (automatch é
    # dry_run por padrão + tela de preview antes de aplicar vínculo).
    # Boost para containment de prefixo (nomes colados/abreviados já validados
    # pelo guarda de token): 'atriumvix' contém 'atrium', 'zaccabrasil' contém
    # 'zacca'. Sem espaços, prefixo do lado mais curto (>=5 chars).
    aj, bj = a.replace(" ", ""), b.replace(" ", "")
    curto, longo = sorted([aj, bj], key=len)
    boost = 0.92 if (len(curto) >= 5 and longo.startswith(curto)) else 0.0

    return max(base, boost)


# Thresholds (calibráveis): auto-vínculo só com alta confiança e sem ambiguidade.
AUTO_MIN = 0.90
SUGESTAO_MIN = 0.70
MARGEM_MIN = 0.08


def classificar(candidatos: list[tuple[float, str, str]]) -> str:
    """Recebe candidatos já ordenados por score desc (score, task_id, nome).
    Retorna 'auto' | 'sugestao' | 'sem_candidato'."""
    if not candidatos or candidatos[0][0] < SUGESTAO_MIN:
        return "sem_candidato"
    melhor = candidatos[0][0]
    segundo = candidatos[1][0] if len(candidatos) > 1 else 0.0
    if melhor >= AUTO_MIN and (melhor - segundo) >= MARGEM_MIN:
        return "auto"
    return "sugestao"


def melhores_candidatos(
    nome_cliente: str,
    cup_rows: list[dict],
    k: int = 5,
) -> list[tuple[float, str, str]]:
    """Top-k (score, task_id, nome) de cup_rows (cada um {'task_id','nome'})."""
    ranked = [
        (score(nome_cliente, r["nome"]), r["task_id"], r["nome"])
        for r in cup_rows
        if r.get("nome")
    ]
    ranked.sort(key=lambda t: t[0], reverse=True)
    return ranked[:k]


# ── Resolução do responsável de Performance ──────────────────────────────
_STATUS_PRIORIDADE = {
    "ativo": 0,
    "onboarding": 1, "pausado": 1, "em cancelamento": 1,
    "entregue": 2,
}


def _status_rank(status: str | None) -> int:
    return _STATUS_PRIORIDADE.get((status or "").strip().lower(), 3)


def _data_key(d: object) -> _date:
    return d if isinstance(d, _date) else _date.min


def responsavel_performance(contratos: list[dict]) -> str | None:
    """Dado os contratos de um cliente (cada um {'servico','status',
    'responsavel','data_inicio'}), escolhe o contrato de Performance vigente
    mais recente e retorna o responsável (ou None)."""
    perf = [
        c for c in contratos
        if "performance" in (c.get("servico") or "").lower()
        and (c.get("responsavel") or "").strip()
    ]
    if not perf:
        return None
    # ordenação estável em dois passos: data desc, depois status asc domina
    perf.sort(key=lambda c: _data_key(c.get("data_inicio")), reverse=True)
    perf.sort(key=lambda c: _status_rank(c.get("status")))
    return perf[0]["responsavel"].strip()
