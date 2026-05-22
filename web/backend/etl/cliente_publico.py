"""Adapter: lê campos da vitrine pública a partir de `Cliente.extras` do core."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


_TRUE_VALUES = {"TRUE", "VERDADEIRO", "SIM", "X", "1", "Y", "YES"}

# Colunas da Planilha Central usadas pela vitrine. Lidas a partir de `Cliente.extras`,
# que já contém todas as colunas não conhecidas pelo core (case-insensitive via _parse_header).
COL_PUBLICAR_VITRINE = "PUBLICAR_VITRINE"
COL_DESCRICAO_PUBLICA = "DESCRICAO_PUBLICA"
COL_LOGO_URL = "LOGO_URL"
COL_SETOR_PUBLICO = "SETOR_PUBLICO"
COL_PORTE_PUBLICO = "PORTE_PUBLICO"


def slugify(nome: str) -> str:
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "cliente"


@dataclass
class ClientePublico:
    """View pública de um Cliente do core, com campos da vitrine extraídos do extras."""

    nome: str
    slug: str
    categoria: str
    publicar_vitrine: bool
    logo_url: str | None
    descricao_publica: str | None
    setor: str | None
    porte: str | None
    cliente_core: object  # Mantém referência ao Cliente original do core para o handler

    @classmethod
    def from_cliente(cls, cliente) -> "ClientePublico":
        extras = getattr(cliente, "extras", {}) or {}
        return cls(
            nome=cliente.nome,
            slug=slugify(cliente.nome),
            categoria=cliente.categoria,
            publicar_vitrine=_is_true(extras.get(COL_PUBLICAR_VITRINE)),
            logo_url=_or_none(extras.get(COL_LOGO_URL)),
            descricao_publica=_or_none(extras.get(COL_DESCRICAO_PUBLICA)),
            setor=_or_none(extras.get(COL_SETOR_PUBLICO)),
            porte=_or_none(extras.get(COL_PORTE_PUBLICO)),
            cliente_core=cliente,
        )


def _is_true(val) -> bool:
    if val is None:
        return False
    return str(val).strip().upper() in _TRUE_VALUES


def _or_none(val) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s or None
