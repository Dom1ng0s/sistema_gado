import pytest
import mysql.connector
from app import app as flask_app
from werkzeug.security import generate_password_hash

# Credenciais fixas para o banco local de teste — isolado do .env de produção
DB_HOST = "localhost"
DB_USER = "gado_test"
DB_PASSWORD = "gado123"
DB_PORT = 3306
TEST_DB_NAME = "sistema_gado_test"

DB_CONFIG = {
    "host": DB_HOST,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "port": DB_PORT,
}

@pytest.fixture(scope='session')
def db_setup():
    """Cria o banco de dados de teste e as tabelas/views."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")
        cursor.execute(f"CREATE DATABASE {TEST_DB_NAME}")
        cursor.execute(f"USE {TEST_DB_NAME}")

        # --- TABELAS ---
        cursor.execute("""
        CREATE TABLE usuarios (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL
        )""")

        cursor.execute("""
        CREATE TABLE animais (
            id INT AUTO_INCREMENT PRIMARY KEY,
            brinco VARCHAR(50) NOT NULL,
            sexo CHAR(1) NOT NULL,
            data_compra DATE NOT NULL,
            preco_compra DECIMAL(10, 2),
            data_venda DATE,
            preco_venda DECIMAL(10, 2),
            user_id INT NOT NULL,
            lote_id INT,
            deleted_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES usuarios(id)
        )""")

        cursor.execute("""
        CREATE TABLE pesagens (
            id INT AUTO_INCREMENT PRIMARY KEY,
            animal_id INT NOT NULL,
            data_pesagem DATE NOT NULL,
            peso DECIMAL(10, 2) NOT NULL,
            deleted_at DATETIME,
            FOREIGN KEY (animal_id) REFERENCES animais(id)
        )""")

        cursor.execute("""
        CREATE TABLE medicacoes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            animal_id INT NOT NULL,
            data_aplicacao DATE NOT NULL,
            nome_medicamento VARCHAR(100) NOT NULL,
            custo DECIMAL(10, 2),
            observacoes TEXT,
            FOREIGN KEY (animal_id) REFERENCES animais(id)
        )""")

        cursor.execute("""
        CREATE TABLE custos_operacionais (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            categoria VARCHAR(20) NOT NULL,
            tipo_custo VARCHAR(50) NOT NULL,
            valor DECIMAL(10, 2) NOT NULL,
            data_custo DATE NOT NULL,
            descricao TEXT,
            deleted_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES usuarios(id)
        )""")

        cursor.execute("""
        CREATE TABLE lotes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            codigo_lote VARCHAR(50) NOT NULL,
            descricao TEXT,
            data_aquisicao DATE,
            FOREIGN KEY (user_id) REFERENCES usuarios(id)
        )""")

        cursor.execute("""
        CREATE TABLE financial_schedule (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            descricao VARCHAR(255) NOT NULL,
            valor DECIMAL(10, 2) NOT NULL,
            vencimento DATE NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pendente',
            deleted_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES usuarios(id)
        )""")

        cursor.execute("""
        CREATE TABLE configuracoes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL UNIQUE,
            nome_fazenda VARCHAR(100),
            cidade_estado VARCHAR(100),
            area_total DECIMAL(10, 2),
            FOREIGN KEY (user_id) REFERENCES usuarios(id)
        )""")

        cursor.execute("""
        CREATE TABLE cost_centers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nome VARCHAR(100) NOT NULL,
            categoria VARCHAR(20) NOT NULL
        )""")

        cursor.executemany(
            "INSERT INTO cost_centers (nome, categoria) VALUES (%s, %s)",
            [
                ('Arrendamento', 'Fixo'),
                ('Salário', 'Fixo'),
                ('Nutrição', 'Variável'),
                ('Veterinário', 'Variável'),
                ('Agendamento', 'Variável'),
            ]
        )

        # --- VIEWS (mocks) ---
        cursor.execute("""
        CREATE VIEW v_gmd_analitico AS
        SELECT a.user_id, a.id AS animal_id,
               0 AS peso_final, 0 AS ganho_total, 0 AS dias, 0 AS gmd
        FROM animais a
        """)

        cursor.execute("""
        CREATE VIEW v_fluxo_caixa AS
        SELECT id AS user_id, 2024 AS ano,
               0 AS total_entradas, 0 AS total_compras,
               0 AS total_med, 0 AS total_ops
        FROM usuarios
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
    })

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
