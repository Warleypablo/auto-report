"""Entry point para o cron de produção: `python -m etl.schedule`."""
import logging
import sys

from .collect import run_etl

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def main() -> int:
    resumo = run_etl()
    print(f"ETL finalizado: {resumo}")
    if resumo.get("fail", 0) > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
