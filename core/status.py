# core/status.py
from __future__ import annotations

from datetime import date
from googleapiclient.errors import HttpError
from utils.logger import get_logger            # type: ignore
from core.leitura_central import (             # type: ignore
    _get_sheets_service,
    _update_status_cell,
    _col_to_letter,
)                                              # type: ignore
from utils.retry import execute_with_retries

log = get_logger(__name__)



# ────────────────────────────────────────────────────────────────────────────────
# STATUS (AUTO)
# ────────────────────────────────────────────────────────────────────────────────
def set_status(cliente, msg: str) -> None:   # noqa: ANN001
    """Escreve *msg* na célula STATUS (AUTO) do cliente."""
    meta = getattr(cliente, "extras", {})
    sid, tab, row, col = (
        meta.get("_sheet_id"),
        meta.get("_tab"),
        meta.get("_row"),
        meta.get("_status_idx"),
    )
    if None in {sid, tab, row, col}:          # linha não tem STATUS
        return
    try:
        service = _get_sheets_service()
        _update_status_cell(service, sid, tab, row, col, msg)
    except HttpError as exc:
        log.error("Falha ao gravar STATUS (%s): %s", cliente.nome, exc)


# ────────────────────────────────────────────────────────────────────────────────
# ULTIMA VEZ GERADO (AUTO)
# ────────────────────────────────────────────────────────────────────────────────
_HEADER_ALVO = "ULTIMA VEZ GERADO (AUTO)"


def _descobrir_coluna_lastgen(service, sid: str, tab: str) -> int | None:
    """Retorna o índice (1-based) da coluna 'ULTIMA VEZ GERADO (AUTO)'. """
    header_range = f"'{tab}'!1:1"
    res = execute_with_retries(
        lambda: service.spreadsheets()
            .values()
            .get(spreadsheetId=sid, range=header_range)
            .execute(),
        logger=log,
        context=f"sheets.values().get (sid={sid}, range={header_range})"
    )
    header = res.get("values", [[]])[0]
    for idx, titulo in enumerate(header, start=1):
        if titulo.strip().lower() == _HEADER_ALVO.lower():
            return idx
    return None


def set_last_generated(cliente, quando: date) -> None:  # noqa: ANN001
    """
    Registra a data (DD/MM/AAAA) da última geração bem-sucedida
    na coluna 'ULTIMA VEZ GERADO (AUTO)'.
    """
    meta = getattr(cliente, "extras", {})
    sid, tab, row, col = (
        meta.get("_sheet_id"),
        meta.get("_tab"),
        meta.get("_row"),
        meta.get("_lastgen_idx"),  # opcional: pode vir vazio
    )

    # Se faltar info essencial, aborta silenciosamente
    if None in {sid, tab, row}:
        return

    try:
        service = _get_sheets_service()

        # Descobre a coluna se ainda não possuímos o índice
        if col is None:
            col = _descobrir_coluna_lastgen(service, sid, tab)
            if col is None:
                log.error(
                    "Coluna '%s' não encontrada na aba %s",
                    _HEADER_ALVO,
                    tab,
                )
                return
            # Armazena para reutilizar em execuções futuras
            meta["_lastgen_idx"] = col

        _update_status_cell(
            service,
            sid,
            tab,
            row,
            col,
            quando.strftime("%d/%m/%Y"),
        )

    except HttpError as exc:
        log.error(
            "Falha ao gravar '%s' (%s): %s",
            _HEADER_ALVO,
            cliente.nome,
            exc,
        )


# ────────────────────────────────────────────────────────────────────────────────
# BATCH: STATUS + ULTIMA VEZ GERADO em uma única chamada Sheets
# ────────────────────────────────────────────────────────────────────────────────
def set_status_e_lastgen(cliente, msg: str, quando: date) -> None:
    """Grava STATUS (AUTO) e ULTIMA VEZ GERADO (AUTO) em uma única chamada batchUpdate."""
    meta = getattr(cliente, "extras", {})
    sid, tab, row, status_col = (
        meta.get("_sheet_id"),
        meta.get("_tab"),
        meta.get("_row"),
        meta.get("_status_idx"),
    )
    if None in {sid, tab, row, status_col}:
        return

    lastgen_col = meta.get("_lastgen_idx")

    try:
        service = _get_sheets_service()

        if lastgen_col is None:
            lastgen_col = _descobrir_coluna_lastgen(service, sid, tab)
            if lastgen_col is not None:
                meta["_lastgen_idx"] = lastgen_col

        data = [{"range": f"{tab}!{_col_to_letter(status_col)}{row}", "values": [[msg]]}]
        if lastgen_col is not None:
            data.append({"range": f"{tab}!{_col_to_letter(lastgen_col)}{row}", "values": [[quando.strftime("%d/%m/%Y")]]})

        execute_with_retries(
            lambda: service.spreadsheets().values().batchUpdate(
                spreadsheetId=sid,
                body={"data": data, "valueInputOption": "RAW"},
            ).execute(),
            logger=log,
            context=f"sheets.batchUpdate (status+lastgen, row={row})",
        )
        log.info("STATUS='%s' e ULTIMA VEZ GERADO gravados em lote (%s)", msg, tab)
    except HttpError as exc:
        log.error("Falha ao gravar status+lastgen (%s): %s", getattr(cliente, "nome", "?"), exc)
