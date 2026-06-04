"""Re-sincroniza staging.cup_clientes / staging.cup_contratos a partir da fonte
viva do ClickUp (banco `dados_turbo`, schema "Clickup").

Contexto: a tabela `staging.cup_*` do banco do app é uma CÓPIA do ClickUp,
alimentada por um ETL externo. Quando esse ETL para, o app passa a mostrar
gestores/contratos velhos (ex.: gestor que já saiu da empresa). Este script é o
ETL: copia o estado atual da fonte para a staging que o app lê.

Características:
- Idempotente: pode rodar quantas vezes quiser; sempre espelha a fonte.
- Seguro: lê TODA a fonte antes de tocar no destino (se a fonte falhar, o
  destino fica intacto); substitui dentro de uma transação (rollback em erro);
  guarda um backup reversível da última versão (`<tabela>_bkp_resync`).
- Resiliente a schema: copia apenas as colunas que existem em AMBOS os lados.
- Sem segredo no código: credenciais vêm de variáveis de ambiente.

Uso:
    CUP_SOURCE_URL='postgresql://USER:PASS@HOST:5432/dados_turbo' \\
    CUP_DEST_URL='postgresql://USER:PASS@HOST:5432/autoreport' \\
    python -m scripts.sync_staging_clickup

`CUP_DEST_URL` é opcional — sem ela, usa `settings.database_url` (o próprio app).
`CUP_SOURCE_SCHEMA` é opcional (default "Clickup").

Agendável (ex.: Render Cron Job) para manter a staging sempre fresca.
"""

from __future__ import annotations

import logging
import os
import sys

import psycopg
from psycopg import sql

_log = logging.getLogger("sync_staging_clickup")

# Tabelas a espelhar e a chave primária de cada uma (no destino).
TABELAS = ("cup_clientes", "cup_contratos")
PK = {"cup_clientes": "task_id", "cup_contratos": "id_subtask"}


def _dsn(url: str) -> str:
    """psycopg não aceita o sufixo `+psycopg` que o SQLAlchemy usa na URL."""
    return url.replace("+psycopg", "")


def _colunas(cur, schema: str, tabela: str) -> list[str]:
    cur.execute(
        """SELECT column_name FROM information_schema.columns
           WHERE table_schema = %s AND table_name = %s
           ORDER BY ordinal_position""",
        (schema, tabela),
    )
    return [r[0] for r in cur.fetchall()]


def sincronizar(
    source_url: str,
    dest_url: str,
    *,
    source_schema: str = "Clickup",
    dest_schema: str = "staging",
) -> dict:
    """Espelha `source_schema.cup_*` (fonte) em `dest_schema.cup_*` (destino).

    Retorna um resumo `{tabela: {"antes", "depois", "colunas"}}`.
    """
    resumo: dict = {}
    with psycopg.connect(_dsn(source_url)) as src, psycopg.connect(_dsn(dest_url)) as dst:
        scur, dcur = src.cursor(), dst.cursor()
        for tabela in TABELAS:
            src_cols = set(_colunas(scur, source_schema, tabela))
            dst_cols = _colunas(dcur, dest_schema, tabela)
            # Ordem do destino, só as colunas presentes em ambos os lados.
            cols = [c for c in dst_cols if c in src_cols]
            pk = PK[tabela]
            if pk not in cols:
                raise RuntimeError(
                    f"{tabela}: PK '{pk}' ausente na interseção de colunas "
                    f"(fonte={sorted(src_cols)}, destino={dst_cols})"
                )

            # Lê TODA a fonte antes de tocar no destino: se a fonte cair aqui,
            # o destino permanece intacto.
            sel = sql.SQL("SELECT {cols} FROM {sch}.{tbl}").format(
                cols=sql.SQL(", ").join(map(sql.Identifier, cols)),
                sch=sql.Identifier(source_schema),
                tbl=sql.Identifier(tabela),
            )
            scur.execute(sel)
            rows = scur.fetchall()

            # A PK precisa ser não-nula e única, senão o INSERT no destino quebra.
            pk_idx = cols.index(pk)
            chaves = [r[pk_idx] for r in rows]
            if any(k is None or (isinstance(k, str) and not k.strip()) for k in chaves):
                raise RuntimeError(f"{tabela}: há PK '{pk}' nula/vazia na fonte — abortado")
            if len(set(chaves)) != len(chaves):
                raise RuntimeError(f"{tabela}: há PK '{pk}' duplicada na fonte — abortado")

            antes = dcur.execute(
                sql.SQL("SELECT COUNT(*) FROM {sch}.{tbl}").format(
                    sch=sql.Identifier(dest_schema), tbl=sql.Identifier(tabela)
                )
            ).fetchone()[0]

            # Backup reversível (sobrescreve o da última sincronização).
            bkp = f"{tabela}_bkp_resync"
            dcur.execute(
                sql.SQL("DROP TABLE IF EXISTS {sch}.{b}").format(
                    sch=sql.Identifier(dest_schema), b=sql.Identifier(bkp)
                )
            )
            dcur.execute(
                sql.SQL("CREATE TABLE {sch}.{b} AS SELECT * FROM {sch}.{tbl}").format(
                    sch=sql.Identifier(dest_schema),
                    b=sql.Identifier(bkp),
                    tbl=sql.Identifier(tabela),
                )
            )
            dst.commit()

            # Substitui o conteúdo de forma atômica.
            try:
                dcur.execute(
                    sql.SQL("TRUNCATE {sch}.{tbl}").format(
                        sch=sql.Identifier(dest_schema), tbl=sql.Identifier(tabela)
                    )
                )
                ins = sql.SQL("INSERT INTO {sch}.{tbl} ({cols}) VALUES ({ph})").format(
                    sch=sql.Identifier(dest_schema),
                    tbl=sql.Identifier(tabela),
                    cols=sql.SQL(", ").join(map(sql.Identifier, cols)),
                    ph=sql.SQL(", ").join(sql.Placeholder() * len(cols)),
                )
                dcur.executemany(ins, rows)
                dst.commit()
            except Exception:
                dst.rollback()
                _log.exception("%s: erro ao gravar — rollback, destino inalterado", tabela)
                raise

            depois = dcur.execute(
                sql.SQL("SELECT COUNT(*) FROM {sch}.{tbl}").format(
                    sch=sql.Identifier(dest_schema), tbl=sql.Identifier(tabela)
                )
            ).fetchone()[0]
            resumo[tabela] = {"antes": antes, "depois": depois, "colunas": len(cols)}
            _log.info(
                "%s: %d → %d linhas (%d colunas; backup em %s.%s)",
                tabela, antes, depois, len(cols), dest_schema, bkp,
            )
    return resumo


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    source_url = os.getenv("CUP_SOURCE_URL")
    if not source_url:
        _log.error(
            "CUP_SOURCE_URL não definida "
            "(ex.: postgresql://USER:PASS@HOST:5432/dados_turbo)"
        )
        return 2

    dest_url = os.getenv("CUP_DEST_URL")
    if not dest_url:
        try:
            from app_settings import get_settings

            dest_url = get_settings().database_url
            _log.info("CUP_DEST_URL não definida — usando settings.database_url do app")
        except Exception:
            _log.exception("CUP_DEST_URL ausente e falhou ao ler settings.database_url")
            return 2

    source_schema = os.getenv("CUP_SOURCE_SCHEMA", "Clickup")
    resumo = sincronizar(source_url, dest_url, source_schema=source_schema)
    _log.info("Sincronização concluída: %s", resumo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
