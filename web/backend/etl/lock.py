from __future__ import annotations

import contextlib
import hashlib

from sqlalchemy import text
from sqlalchemy.engine import Engine


class LockTaken(Exception):
    pass


def _key_to_bigint(key: str) -> int:
    h = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big", signed=True)


@contextlib.contextmanager
def advisory_lock(engine: Engine, key: str, *, blocking: bool = True):
    bigint = _key_to_bigint(key)
    conn = engine.connect()
    try:
        if blocking:
            conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": bigint})
        else:
            got = conn.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": bigint})
            if not got:
                raise LockTaken(f"Lock {key!r} ocupado")
        yield
        conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": bigint})
    finally:
        conn.close()
