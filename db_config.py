"""Camada de conexão com o PostgreSQL (psycopg 3 + pool).

SQL puro, sem ORM (ver CLAUDE.md). A interface pública — `get_db_connection`,
`close_db_connection`, `get_db_cursor` — é a mesma de quando o banco era MySQL;
os repositórios não sabem qual driver está embaixo.
"""
import logging
import os
from contextlib import contextmanager

import psycopg
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("db_config")

load_dotenv()

# Exceções expostas para as rotas não importarem psycopg diretamente.
IntegrityError = psycopg.IntegrityError
UniqueViolation = psycopg.errors.UniqueViolation

# conftest.py sobrescreve este dict e chama reset_pool() para apontar ao banco de teste.
db_settings = {
    "host": os.getenv('DB_HOST'),
    "user": os.getenv('DB_USER'),
    "password": os.getenv('DB_PASSWORD'),
    "database": os.getenv('DB_NAME'),
    "port": int(os.getenv('DB_PORT', 5432)),
}

_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', 5))


def _conn_kwargs():
    """Parâmetros de conexão para o psycopg. Railway expõe DATABASE_URL no plugin
    Postgres; se setada, tem prioridade sobre as DB_* (que valem em dev)."""
    url = os.getenv('DATABASE_URL')
    if url:
        return {"conninfo": url.replace('postgres://', 'postgresql://', 1)}
    kw = {
        "host": db_settings.get('host'),
        "port": db_settings.get('port'),
        "user": db_settings.get('user'),
        "password": db_settings.get('password'),
        "dbname": db_settings.get('database'),
        "connect_timeout": 10,
    }
    return {"kwargs": {k: v for k, v in kw.items() if v is not None}}


def _new_pool():
    try:
        cfg = _conn_kwargs()
        p = ConnectionPool(
            cfg.get("conninfo", ""),
            kwargs=cfg.get("kwargs"),
            name="gado_pool",
            min_size=1,
            max_size=_POOL_SIZE,
            timeout=10,
            open=False,
        )
        p.open()
        logger.info(" Pool PostgreSQL ativo (%d conexões máx).", _POOL_SIZE)
        return p
    except Exception as e:  # noqa: BLE001 — degradar para conexão avulsa
        logger.warning(" AVISO: falha ao criar o pool: %s", e)
        return None


connection_pool = _new_pool()


def reset_pool():
    """Descarta o pool atual e cria um novo. Usado no post_fork do Gunicorn
    (sockets herdados do master não sobrevivem ao fork) e no conftest."""
    global connection_pool
    old = connection_pool
    connection_pool = _new_pool()
    if old is not None:
        try:
            old.close()
        except Exception:
            pass


def get_db_connection():
    """Conexão do pool (ou avulsa, se o pool falhou). Devolve None em erro —
    contrato herdado; models.py e helpers de teste checam `if conn`."""
    try:
        if connection_pool is not None:
            return connection_pool.getconn()
        cfg = _conn_kwargs()
        return psycopg.connect(cfg.get("conninfo", ""), **(cfg.get("kwargs") or {}))
    except Exception as e:  # noqa: BLE001
        logger.error(" ERRO CRÍTICO DE CONEXÃO: %s", e)
        return None


def close_db_connection(connection):
    """Devolve a conexão ao pool (ou fecha, se avulsa)."""
    if connection is None:
        return
    if connection_pool is not None:
        try:
            connection_pool.putconn(connection)
            return
        except Exception:
            pass
    try:
        connection.close()
    except Exception:
        pass


@contextmanager
def get_db_cursor():
    """Cursor transacional: commit no sucesso, rollback na exceção, conexão
    sempre devolvida ao pool."""
    conn = get_db_connection()
    if conn is None:
        raise ConnectionError("Falha na conexão com BD")
    try:
        with conn.cursor() as cursor:
            yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        close_db_connection(conn)
