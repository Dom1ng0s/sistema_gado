import os
import pytest
import psycopg
from app import app as flask_app
from werkzeug.security import generate_password_hash
from db_migrate import apply_migrations, database_url

# Credenciais fixas para o banco local de teste — isolado do .env de produção.
# Suportam override via variáveis de ambiente (útil para CI e instâncias temporárias).
DB_HOST = os.getenv("TEST_DB_HOST", "localhost")
DB_USER = os.getenv("TEST_DB_USER", "gado")
DB_PASSWORD = os.getenv("TEST_DB_PASSWORD", "gado123")
DB_PORT = int(os.getenv("TEST_DB_PORT", "5432"))
TEST_DB_NAME = os.getenv("TEST_DB_NAME", "sistema_gado_test")

# kwargs no formato do psycopg (dbname, não database). Testes que abrem conexão
# própria importam TEST_DB_CONFIG daqui em vez de repetir credenciais.
TEST_DB_CONFIG = {
    "host": DB_HOST,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "port": DB_PORT,
    "dbname": TEST_DB_NAME,
}


@pytest.fixture(scope='session')
def db_setup():
    """Cria o banco de teste e aplica as MESMAS migrations de produção
    (migrations/*.sql via yoyo), evitando manter duas cópias do DDL."""
    try:
        # DROP/CREATE DATABASE exige conexão a outro banco e autocommit.
        admin = psycopg.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, port=DB_PORT,
            dbname="postgres", autocommit=True,
        )
        with admin.cursor() as cur:
            cur.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)')
            cur.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
        admin.close()

        apply_migrations(url=database_url(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD,
            port=DB_PORT, database=TEST_DB_NAME,
        ))

        conn = psycopg.connect(**TEST_DB_CONFIG)
        with conn.cursor() as cur:
            # As 3 materialized views (migration 0003) viram VIEW normal sobre o
            # mesmo corpo (`*_live`) só nos testes — recupera consistência
            # read-after-write sem recopiar SQL. Em produção continuam matview
            # com REFRESH agendado (app.py). Ver #115.
            for mv in ("v_gmd_analitico", "v_fluxo_caixa", "vw_resultado_lote"):
                cur.execute(f"DROP MATERIALIZED VIEW IF EXISTS {mv} CASCADE")
                cur.execute(f"CREATE VIEW {mv} AS SELECT * FROM {mv}_live")

            senha_hash = generate_password_hash('123')
            cur.execute(
                "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
                ('testuser', senha_hash),
            )
        conn.commit()
        conn.close()
    except Exception as e:
        pytest.fail(f"Erro ao configurar DB de teste: {e}")

    yield


@pytest.fixture
def app(db_setup):
    """Fixture obrigatória: retorna a instância do app apontando para o banco de teste."""
    flask_app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "RATELIMIT_ENABLED": False,
    })
    # RATELIMIT_ENABLED no config não afeta limiter.enabled (instance attr definido no init).
    from extensions import limiter as _limiter
    _limiter.enabled = False

    import db_config
    db_config.db_settings.update({
        "host": DB_HOST,
        "user": DB_USER,
        "password": DB_PASSWORD,
        "port": DB_PORT,
        "database": TEST_DB_NAME,
    })
    db_config.reset_pool()

    yield flask_app


@pytest.fixture
def client(app):
    """Retorna o cliente de teste simulando um navegador."""
    return app.test_client()
