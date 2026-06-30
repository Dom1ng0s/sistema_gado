import os
import pytest
import mysql.connector
from app import app as flask_app
from werkzeug.security import generate_password_hash

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
            password_hash VARCHAR(255) NOT NULL,
            email VARCHAR(255) NULL
        )""")

        cursor.execute("""
        CREATE TABLE animais (
            id INT AUTO_INCREMENT PRIMARY KEY,
            brinco VARCHAR(50) NOT NULL,
            sexo CHAR(1) NOT NULL,
            raca VARCHAR(100) NULL,
            data_compra DATE NOT NULL,
            data_nascimento DATE NULL,
            preco_compra DECIMAL(10, 2),
            data_venda DATE,
            preco_venda DECIMAL(10, 2),
            user_id INT NOT NULL,
            lote_id INT,
            deleted_at DATETIME,
            pai_id INT NULL,
            mae_id INT NULL,
            FOREIGN KEY (user_id) REFERENCES usuarios(id),
            FOREIGN KEY (pai_id) REFERENCES animais(id) ON DELETE SET NULL,
            FOREIGN KEY (mae_id) REFERENCES animais(id) ON DELETE SET NULL
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
            deleted_at DATETIME NULL DEFAULT NULL,
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
            deleted_at DATETIME NULL DEFAULT NULL,
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

        # --- TABELAS DE HEREDITARIEDADE ---
        cursor.execute("""
        CREATE TABLE reproducao (
            id INT AUTO_INCREMENT PRIMARY KEY,
            vaca_id INT NOT NULL,
            touro_id INT NULL,
            touro_externo VARCHAR(200) NULL,
            data_cobertura DATE NOT NULL,
            diagnostico ENUM('pendente','positivo','negativo') DEFAULT 'pendente',
            data_diagnostico DATE NULL,
            data_parto_prevista DATE NULL,
            data_parto DATE NULL,
            resultado ENUM('vivo','natimorto','aborto') NOT NULL,
            user_id INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vaca_id) REFERENCES animais(id) ON DELETE CASCADE,
            FOREIGN KEY (touro_id) REFERENCES animais(id) ON DELETE SET NULL,
            FOREIGN KEY (user_id) REFERENCES usuarios(id)
        )""")

        # --- TABELAS DE GESTÃO DE PASTOS ---
        cursor.execute("""
        CREATE TABLE pastos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            nome VARCHAR(100) NOT NULL,
            area_hectares DECIMAL(10,2),
            forrageira VARCHAR(100),
            capacidade_ua DECIMAL(10,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )""")

        cursor.execute("""
        CREATE TABLE modulos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            pasto_id INT NOT NULL,
            user_id INT NOT NULL,
            nome VARCHAR(100) NOT NULL,
            area_hectares DECIMAL(10,2),
            capacidade_ua DECIMAL(10,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pasto_id) REFERENCES pastos(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES usuarios(id)
        )""")

        cursor.execute("""
        CREATE TABLE ocupacoes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            modulo_id INT NOT NULL,
            user_id INT NOT NULL,
            data_entrada DATE NOT NULL,
            data_saida DATE NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (modulo_id) REFERENCES modulos(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES usuarios(id)
        )""")

        cursor.execute("""
        CREATE TABLE ocupacao_animais (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ocupacao_id INT NOT NULL,
            animal_id INT NOT NULL,
            FOREIGN KEY (ocupacao_id) REFERENCES ocupacoes(id) ON DELETE CASCADE,
            FOREIGN KEY (animal_id) REFERENCES animais(id) ON DELETE CASCADE
        )""")

        # --- VIEWS (mocks) ---
        cursor.execute("""
        CREATE VIEW v_gmd_analitico AS
        SELECT a.user_id, a.id AS animal_id,
               0 AS peso_final, 0 AS ganho_total, 0 AS dias, 0 AS gmd
        FROM animais a
        """)

        cursor.execute("""
        CREATE VIEW vw_ocupacao_atual AS
        SELECT
            m.id AS modulo_id, m.pasto_id, m.user_id, m.nome AS modulo_nome,
            m.capacidade_ua, o.id AS ocupacao_id, o.data_entrada,
            COUNT(oa.animal_id) AS ua_atual,
            ROUND(COUNT(oa.animal_id) / NULLIF(m.capacidade_ua, 0) * 100, 1) AS pct_lotacao
        FROM modulos m
        JOIN ocupacoes o ON o.modulo_id = m.id AND o.data_saida IS NULL
        JOIN ocupacao_animais oa ON oa.ocupacao_id = o.id
        GROUP BY m.id, m.pasto_id, m.user_id, m.nome, m.capacidade_ua, o.id, o.data_entrada
        """)

        cursor.execute("""
        CREATE VIEW vw_dias_descanso AS
        SELECT
            m.id AS modulo_id, m.pasto_id, m.user_id, m.nome AS modulo_nome,
            MAX(o.data_saida) AS ultima_saida,
            DATEDIFF(CURDATE(), MAX(o.data_saida)) AS dias_descanso
        FROM modulos m
        LEFT JOIN ocupacoes o ON o.modulo_id = m.id AND o.data_saida IS NOT NULL
        WHERE m.id NOT IN (SELECT modulo_id FROM ocupacoes WHERE data_saida IS NULL)
        GROUP BY m.id, m.pasto_id, m.user_id, m.nome
        """)

        cursor.execute("""
        CREATE VIEW vw_gmd_por_modulo AS
        SELECT
            o.modulo_id, m.nome AS modulo_nome, m.pasto_id, m.user_id,
            COUNT(DISTINCT oa.animal_id) AS qtd_animais,
            ROUND(AVG(g.gmd), 3) AS gmd_medio
        FROM ocupacoes o
        JOIN ocupacao_animais oa ON oa.ocupacao_id = o.id
        JOIN modulos m ON m.id = o.modulo_id
        LEFT JOIN v_gmd_analitico g ON g.animal_id = oa.animal_id
        GROUP BY o.modulo_id, m.nome, m.pasto_id, m.user_id
        """)

        cursor.execute("""
        CREATE VIEW v_fluxo_caixa AS
        SELECT id AS user_id, 2024 AS ano,
               0 AS total_entradas, 0 AS total_compras,
               0 AS total_med, 0 AS total_ops
        FROM usuarios
        """)

        cursor.execute("""
        CREATE VIEW vw_gmd_por_touro AS
        SELECT
            pai.id AS touro_id, pai.brinco AS touro_brinco, pai.user_id,
            COUNT(DISTINCT filho.id) AS qtd_filhos,
            ROUND(AVG(g.gmd), 3) AS gmd_medio_filhos
        FROM animais pai
        JOIN animais filho ON filho.pai_id = pai.id AND filho.deleted_at IS NULL
        LEFT JOIN v_gmd_analitico g ON g.animal_id = filho.id
        WHERE pai.deleted_at IS NULL
        GROUP BY pai.id, pai.brinco, pai.user_id
        """)

        cursor.execute("""
        CREATE VIEW vw_historico_vaca AS
        SELECT
            r.vaca_id, a.user_id,
            COUNT(*) AS total_coberturas,
            SUM(CASE WHEN r.resultado = 'vivo' THEN 1 ELSE 0 END) AS partos_vivos,
            ROUND(SUM(CASE WHEN r.resultado = 'vivo' THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) AS taxa_sucesso,
            MIN(r.data_cobertura) AS primeira_cobertura,
            MAX(r.data_cobertura) AS ultima_cobertura
        FROM reproducao r
        JOIN animais a ON r.vaca_id = a.id
        GROUP BY r.vaca_id, a.user_id
        """)

        # --- TABELAS DE ESTOQUE VIRTUAL ---
        cursor.execute("""
        CREATE TABLE estoque_produtos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            nome VARCHAR(200) NOT NULL,
            unidade VARCHAR(50) NOT NULL,
            categoria ENUM('medicamento','vacina','suplemento','mineral','outro') NOT NULL DEFAULT 'outro',
            estoque_minimo DECIMAL(10,3) NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )""")

        cursor.execute("""
        CREATE TABLE estoque_movimentacoes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            produto_id INT NOT NULL,
            tipo ENUM('entrada','saida') NOT NULL,
            quantidade DECIMAL(10,3) NOT NULL,
            custo_unitario DECIMAL(10,2) NULL,
            motivo VARCHAR(300) NULL,
            lote_fabricante VARCHAR(100) NULL,
            data_validade DATE NULL,
            data_mov DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES usuarios(id),
            FOREIGN KEY (produto_id) REFERENCES estoque_produtos(id) ON DELETE CASCADE
        )""")

        cursor.execute("""
        CREATE TABLE protocolos_sanitarios (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            nome VARCHAR(200) NOT NULL,
            descricao TEXT,
            intervalo_dias INT NOT NULL,
            proxima_aplicacao DATE NOT NULL,
            ativo TINYINT(1) DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )""")

        cursor.execute("""
        CREATE VIEW vw_partos_previstos AS
        SELECT
            r.id, r.user_id, r.vaca_id,
            v.brinco AS vaca_brinco,
            r.data_cobertura,
            r.data_parto_prevista,
            r.diagnostico,
            DATEDIFF(r.data_parto_prevista, CURDATE()) AS dias_restantes
        FROM reproducao r
        JOIN animais v ON r.vaca_id = v.id AND v.deleted_at IS NULL
        WHERE r.diagnostico = 'positivo'
          AND r.data_parto IS NULL
          AND r.data_parto_prevista IS NOT NULL
        """)

        cursor.execute("""
        CREATE VIEW vw_resultado_lote AS
        SELECT
            l.id AS lote_id,
            l.user_id,
            l.codigo_lote,
            l.descricao,
            l.data_aquisicao,
            COUNT(a.id) AS total_animais,
            COALESCE(SUM(a.preco_compra), 0) AS custo_aquisicao,
            COALESCE(SUM(CASE WHEN a.data_venda IS NOT NULL THEN a.preco_venda END), 0) AS receita_vendas,
            COALESCE(SUM(med.custo_med), 0) AS custo_medicacoes,
            COUNT(CASE WHEN a.data_venda IS NOT NULL THEN 1 END) AS animais_vendidos,
            COALESCE(SUM(CASE WHEN a.data_venda IS NOT NULL THEN a.preco_venda END), 0)
              - COALESCE(SUM(a.preco_compra), 0)
              - COALESCE(SUM(med.custo_med), 0) AS margem_bruta
        FROM lotes l
        JOIN animais a ON a.lote_id = l.id AND a.deleted_at IS NULL
        LEFT JOIN (
            SELECT animal_id, SUM(custo) AS custo_med
            FROM medicacoes WHERE deleted_at IS NULL GROUP BY animal_id
        ) med ON med.animal_id = a.id
        WHERE l.deleted_at IS NULL
        GROUP BY l.id, l.user_id, l.codigo_lote, l.descricao, l.data_aquisicao
        """)

        cursor.execute("""
        CREATE VIEW vw_saldo_estoque AS
        SELECT
            p.id AS produto_id, p.user_id, p.nome, p.unidade, p.categoria, p.estoque_minimo,
            COALESCE(SUM(CASE WHEN m.tipo = 'entrada' THEN m.quantidade ELSE 0 END), 0) AS total_entradas,
            COALESCE(SUM(CASE WHEN m.tipo = 'saida'   THEN m.quantidade ELSE 0 END), 0) AS total_saidas,
            COALESCE(SUM(CASE WHEN m.tipo = 'entrada' THEN m.quantidade ELSE -m.quantidade END), 0) AS saldo_atual,
            CASE
                WHEN COALESCE(SUM(CASE WHEN m.tipo = 'entrada' THEN m.quantidade ELSE -m.quantidade END), 0) < p.estoque_minimo
                THEN 1 ELSE 0
            END AS abaixo_minimo,
            MIN(CASE WHEN m.tipo = 'entrada' AND m.data_validade IS NOT NULL
                     THEN m.data_validade END) AS proxima_validade,
            CASE WHEN MIN(CASE WHEN m.tipo = 'entrada' AND m.data_validade IS NOT NULL
                               THEN m.data_validade END) < CURDATE()
                 THEN 1 ELSE 0 END AS tem_vencido
        FROM estoque_produtos p
        LEFT JOIN estoque_movimentacoes m ON m.produto_id = p.id
        GROUP BY p.id, p.user_id, p.nome, p.unidade, p.categoria, p.estoque_minimo
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
