import pytest
from sqlalchemy import create_engine

from config import get_settings
from etl.lock import LockTaken, advisory_lock


@pytest.fixture
def engine():
    s = get_settings()
    eng = create_engine(s.database_url, future=True)
    yield eng
    eng.dispose()


def test_advisory_lock_basico(engine):
    with advisory_lock(engine, "etl:test:basico"):
        pass


def test_advisory_lock_concorrente(engine):
    with advisory_lock(engine, "etl:test:concorrente"):
        with pytest.raises(LockTaken):
            with advisory_lock(engine, "etl:test:concorrente", blocking=False):
                pytest.fail("não devia ter conseguido")


def test_advisory_lock_libera_apos_sair(engine):
    with advisory_lock(engine, "etl:test:libera"):
        pass
    # Mesma chave imediatamente após — deve obter
    with advisory_lock(engine, "etl:test:libera", blocking=False):
        pass
