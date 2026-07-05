import os
import pytest
import mysql.connector
from app import app as flask_app
from werkzeug.security import generate_password_hash
from init_db import criar_schema

# Credenciais fixas para o banco local de teste — isolado do .env de produção
# Suportam override via variáveis de ambiente (útil para CI e instâncias temporárias)
DB_HOST = os.getenv("TEST_DB_HOST", "localhost")
DB_USER = os.getenv("TEST_DB_USER", "gado_test")
DB_PASSWORD = os.getenv("TEST_DB_PASSWORD", "gado123")
DB_PORT = int(os.getenv("TEST_DB_PORT", "3306"))
TEST_DB_NAME = os.getenv("TEST_DB_NAME", "sistema_gado_test")

DB_CONFIG = {
    "host": DB_HOST,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "port": DB_PORT,
}

@pytest.fixture(scope='session')
def db_setup():
    """Cria o banco de dados de teste e as tabelas/views a partir da mesma
    fonte de verdade usada em produção (init_db.criar_schema), evitando manter
    duas cópias manuais do DDL."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")
        cursor.execute(f"CREATE DATABASE {TEST_DB_NAME}")
        cursor.execute(f"USE {TEST_DB_NAME}")

        criar_schema(cursor)

        # v_gmd_analitico simplificada: retorna gmd=0 para todo animal (mesmo sem
        # 2 pesagens), diferente da view real que exige histórico de pesagem.
        # Repositórios que precisam de GMD real (get_animais_com_gmd, get_gmd_medio_rebanho,
        # get_ranking_touros) já calculam inline sem depender desta view — ver H3 em test_optimizer.py.
        cursor.execute("""
        CREATE OR REPLACE VIEW v_gmd_analitico AS
        SELECT a.user_id, a.id AS animal_id,
               0 AS peso_final, 0 AS ganho_total, 0 AS dias, 0 AS gmd
        FROM animais a
        """)

        # --- DADOS INICIAIS ---
        senha_hash = generate_password_hash('123')
        cursor.execute(
            "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
            ('testuser', senha_hash)
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
    # Precisamos desabilitar diretamente para que os testes não acumulem contadores.
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

    try:
        db_config.connection_pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name="test_pool",
            pool_size=2,
            **db_config.db_settings
        )
    except Exception:
        db_config.connection_pool = None

    yield flask_app


@pytest.fixture
def client(app):
    """Retorna o cliente de teste simulando um navegador."""
    return app.test_client()
