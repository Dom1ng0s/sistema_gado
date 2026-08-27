"""Aplica as migrations SQL versionadas de ``migrations/`` ao banco.

Camada fina sobre *yoyo-migrations*: mantém o schema versionado e auditável sem
introduzir ORM (ver CLAUDE.md — "SQL puro"). O yoyo registra o que já rodou na
tabela ``_yoyo_migration``, então rodar de novo é no-op.

Uso:
    python db_migrate.py            # aplica pendentes no banco do .env (DB_*)
    python db_migrate.py --list     # lista migrations e status
    python db_migrate.py --rollback # desfaz a última (se houver .rollback.sql)

``init_db.py`` e ``conftest.py`` chamam :func:`apply_migrations` diretamente.
"""
import argparse
import os
import warnings
from urllib.parse import quote

from contextlib import contextmanager

from dotenv import load_dotenv
from yoyo import get_backend, read_migrations

load_dotenv()


@contextmanager
def _quiet_pymysql_deprecations():
    # yoyo 9.0 passa db=/passwd= ao PyMySQL (kwargs antigos). Ruído, não é problema nosso.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message=r"'(db|passwd)' is deprecated",
            category=DeprecationWarning,
        )
        yield

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")


def database_url(host=None, user=None, password=None, port=None, database=None):
    """Monta a URL mysql:// do yoyo a partir dos parâmetros ou das vars DB_*."""
    host = host or os.getenv("DB_HOST", "localhost")
    user = user or os.getenv("DB_USER", "")
    password = os.getenv("DB_PASSWORD", "") if password is None else password
    port = port or os.getenv("DB_PORT", "3306")
    database = database or os.getenv("DB_NAME", "")
    # senha pode conter @ : / — sempre percent-encode
    return f"mysql://{user}:{quote(str(password))}@{host}:{port}/{database}"


def apply_migrations(url=None, **conn):
    """Aplica todas as migrations pendentes. Retorna a lista aplicada agora."""
    migrations = read_migrations(MIGRATIONS_DIR)
    with _quiet_pymysql_deprecations():
        backend = get_backend(url or database_url(**conn))
        with backend.lock():
            pending = backend.to_apply(migrations)
            backend.apply_migrations(pending)
    return [m.id for m in pending]


def rollback_last(url=None, **conn):
    migrations = read_migrations(MIGRATIONS_DIR)
    with _quiet_pymysql_deprecations():
        backend = get_backend(url or database_url(**conn))
        with backend.lock():
            applied = backend.to_rollback(migrations)
            last = applied[-1:] if applied else []
            backend.rollback_migrations(last)
    return [m.id for m in last]


def _status(url=None, **conn):
    migrations = read_migrations(MIGRATIONS_DIR)
    with _quiet_pymysql_deprecations():
        backend = get_backend(url or database_url(**conn))
        applied = {m.id for m in backend.to_rollback(migrations)}
    for m in migrations:
        print(f"  [{'x' if m.id in applied else ' '}] {m.id}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="lista migrations e status")
    ap.add_argument("--rollback", action="store_true", help="desfaz a última migration")
    args = ap.parse_args()

    if args.list:
        _status()
    elif args.rollback:
        done = rollback_last()
        print(f"Rollback: {done or 'nada a desfazer'}")
    else:
        done = apply_migrations()
        print(f"Aplicadas: {done or 'nenhuma pendente'}")
