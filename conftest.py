import pytest
import mysql.connector
import os
from app import app as flask_app 
from werkzeug.security import generate_password_hash

# Configurações do Banco de Teste
DB_CONFIG = {
    "host": os.getenv('DB_HOST', 'localhost'),
    "user": os.getenv('DB_USER', 'root'),
    "password": os.getenv('DB_PASSWORD', ''),
    "port": int(os.getenv('DB_PORT', 3306))
}
TEST_DB_NAME = "sistema_gado_test"

@pytest.fixture(scope='session')
def db_setup():
    """Cria o banco de dados de teste e as tabelas/views."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Garante ambiente limpo
        cursor.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")
        cursor.execute(f"CREATE DATABASE {TEST_DB_NAME}")
        cursor.execute(f"USE {TEST_DB_NAME}")
        
        # --- CRIAÇÃO DE TABELAS ---
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
            FOREIGN KEY (user_id) REFERENCES usuarios(id)
        )""")
        
        cursor.execute("""
        CREATE TABLE pesagens (
            id INT AUTO_INCREMENT PRIMARY KEY,
            animal_id INT NOT NULL,
            data_pesagem DATE NOT NULL,
            peso DECIMAL(10, 2) NOT NULL,
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
            FOREIGN KEY (user_id) REFERENCES usuarios(id)
        )""")

        # --- MOCK DE VIEWS (CORRIGIDO) ---
        cursor.execute("""
        CREATE VIEW v_gmd_analitico AS
        SELECT a.user_id, a.id as animal_id, 0 as peso_final, 0 as ganho_total, 0 as dias, 0 as gmd
        FROM animais a
        """) 
        
        # CORREÇÃO AQUI: 'id as user_id' em vez de 'user_id'
        cursor.execute("""
        CREATE VIEW v_fluxo_caixa AS
        SELECT id as user_id, 2024 as ano, 0 as total_entradas, 0 as total_compras, 0 as total_med, 0 as total_ops
        FROM usuarios
        """)

        # --- DADOS INICIAIS ---
        senha_hash = generate_password_hash('123')
        cursor.execute("INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)", ('testuser', senha_hash))
        
        conn.commit()
        conn.close()
    except Exception as e:
        pytest.fail(f"Erro ao configurar DB de teste: {e}")
    
    yield

@pytest.fixture
def app(db_setup):
    """Fixture OBRIGATÓRIA: Retorna a instância do app configurada."""
    flask_app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False
    })
    
    # Redireciona conexão do app para o banco de teste
    import db_config
    db_config.db_settings['database'] = TEST_DB_NAME
    
    # Força recriação do pool
    try:
        db_config.connection_pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name="test_pool",
            pool_size=2,
            **db_config.db_settings
        )
    except:
        db_config.connection_pool = None 

    yield flask_app

@pytest.fixture
def client(app):
    """Retorna o navegador simulado."""
    return app.test_client()