import mysql.connector
import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()


def _connect(retries=5, delay=3):
    cfg = dict(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        port=int(os.getenv('DB_PORT', 3306)),
        connection_timeout=10,
    )
    for attempt in range(1, retries + 1):
        try:
            return mysql.connector.connect(**cfg)
        except mysql.connector.Error as e:
            print(f" Tentativa {attempt}/{retries} falhou: {e}")
            if attempt < retries:
                time.sleep(delay)
    raise RuntimeError("Não foi possível conectar ao banco após várias tentativas.")


def criar_schema(cursor):
    """Cria/atualiza tabelas, colunas, índices e views no banco selecionado por `cursor`.

    Idempotente (IF NOT EXISTS / try-except em ALTERs) — pode ser chamada tanto
    contra um banco de produção já populado (python init_db.py) quanto contra um
    banco de teste recém-criado (conftest.py:db_setup), sempre convergindo para
    o mesmo schema. Não faz commit — quem chama controla a transação.
    """
    # ==============================================================================
    # ETAPA 1: TABELAS FUNDAMENTAIS (Ordem de Dependência: Usuários -> Outros)
    # ==============================================================================

    # 1.1 Tabela USUÁRIOS
    print(" [1/6] Criando tabela 'usuarios'...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL
    );
    """)

    # 1.2 Inserção do ADMIN Padrão
    print(" Verificando usuário 'admin'...")
    hash_admin = 'scrypt:32768:8:1$kXp5C5q9Zz8s$6e28d45f348043653131707572706854199c07172551061919864273347072557766858172970635489708764835940561570198038755030800008853755355'
    try:
        cursor.execute("INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)", ('admin', hash_admin))
        print("   -> Usuário 'admin' criado (Senha: admin123).")
    except mysql.connector.Error as err:
        if err.errno == 1062:
            print("   -> Usuário 'admin' já existe.")
        else:
            raise err

    # 1.3 Tabela ANIMAIS
    print(" [2/6] Criando tabela 'animais'...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS animais (
        id INT AUTO_INCREMENT PRIMARY KEY,
        brinco VARCHAR(50) NOT NULL,
        sexo CHAR(1) NOT NULL,
        data_compra DATE NOT NULL,
        preco_compra DECIMAL(10, 2),
        data_venda DATE,
        preco_venda DECIMAL(10, 2),
        user_id INT NOT NULL,
        deleted_at DATETIME NULL DEFAULT NULL,
        FOREIGN KEY (user_id) REFERENCES usuarios(id),
        UNIQUE KEY idx_brinco_user (brinco, user_id)
    );
    """)

    # 1.4 Tabelas Satélites
    print(" [3/6] Criando tabelas satélites (pesagens, medicacoes, custos)...")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pesagens (
        id INT AUTO_INCREMENT PRIMARY KEY,
        animal_id INT NOT NULL,
        data_pesagem DATE NOT NULL,
        peso DECIMAL(10, 2) NOT NULL,
        deleted_at DATETIME NULL DEFAULT NULL,
        FOREIGN KEY (animal_id) REFERENCES animais(id)
    );
    """)

    print("Criando Tabela Lotes")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lotes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        codigo_lote VARCHAR(50) NOT NULL,
        descricao VARCHAR(200),
        data_aquisicao DATE NOT NULL,
        custo_medio_cabeca DECIMAL(10, 2),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        deleted_at DATETIME NULL DEFAULT NULL,
        FOREIGN KEY (user_id) REFERENCES usuarios(id)
    );
    """)

    print(" Verificando coluna 'lote_id' em 'animais'...")
    try:
        cursor.execute("ALTER TABLE animais ADD COLUMN lote_id INT NULL")
        cursor.execute("ALTER TABLE animais ADD CONSTRAINT fk_animais_lote FOREIGN KEY (lote_id) REFERENCES lotes(id)")
        print("   -> Coluna 'lote_id' adicionada com sucesso.")
    except mysql.connector.Error as err:
        if err.errno == 1060:
            print("   -> Coluna 'lote_id' já existe. Nenhuma alteração necessária.")
        else:
            print(f"    Alerta não crítico: {err}")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS medicacoes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        animal_id INT NOT NULL,
        data_aplicacao DATE NOT NULL,
        nome_medicamento VARCHAR(100) NOT NULL,
        custo DECIMAL(10, 2),
        observacoes TEXT,
        deleted_at DATETIME NULL DEFAULT NULL,
        FOREIGN KEY (animal_id) REFERENCES animais(id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS custos_operacionais (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        categoria VARCHAR(20) NOT NULL,
        tipo_custo VARCHAR(50) NOT NULL,
        valor DECIMAL(10, 2) NOT NULL,
        data_custo DATE NOT NULL,
        descricao TEXT,
        deleted_at DATETIME NULL DEFAULT NULL,
        FOREIGN KEY (user_id) REFERENCES usuarios(id)
    );
    """)

    # 1.4 Tabela CONFIGURAÇÕES
    print("  Criando tabela 'configuracoes'...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS configuracoes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL UNIQUE,
        nome_fazenda VARCHAR(100),
        cidade_estado VARCHAR(100),
        area_total DECIMAL(10, 2),
        FOREIGN KEY (user_id) REFERENCES usuarios(id)
    );
    """)

    # ==============================================================================
    # Sprint 6: GMD meta configurável por usuário
    # ==============================================================================
    try:
        cursor.execute(
            "ALTER TABLE configuracoes ADD COLUMN gmd_meta DECIMAL(5,3) NOT NULL DEFAULT 0.800"
        )
        print("   -> Coluna 'gmd_meta' adicionada.")
    except mysql.connector.Error as err:
        if err.errno == 1060:
            print("   -> Coluna 'gmd_meta' já existe.")
        else:
            print(f"   Alerta 'gmd_meta': {err}")

    print("  Criando tabela 'financial_schedule'...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS financial_schedule (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        descricao VARCHAR(255) NOT NULL,
        valor DECIMAL(10, 2) NOT NULL,
        vencimento DATE NOT NULL,
        status VARCHAR(20) DEFAULT 'pendente',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        deleted_at DATETIME NULL DEFAULT NULL,
        FOREIGN KEY (user_id) REFERENCES usuarios(id)
    );
    """)
    print("Criando tabela 'cost_centers'...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cost_centers (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nome VARCHAR(50) NOT NULL,
        categoria VARCHAR(20) NOT NULL,
        UNIQUE KEY idx_nome_cat (nome, categoria)
    );
    """)

    # 1.4 SEEDER
    print("Populando 'cost_centers'...")
    dados = [
        ('Arrendamento', 'Fixo'), ('Salário', 'Fixo'), ('Manutenção', 'Fixo'), ('Outros', 'Fixo'),
        ('Nutrição', 'Variavel'), ('Sanitário', 'Variavel'), ('Frete', 'Variavel'), ('Outros', 'Variavel')
    ]
    cursor.executemany("INSERT IGNORE INTO cost_centers (nome, categoria) VALUES (%s, %s)", dados)

    # ==============================================================================
    # ETAPA 1.5: ÍNDICES DE PERFORMANCE (OTIMIZAÇÃO)
    # ==============================================================================
    print(" Aplicando índices de performance...")

    indices_sql = [
        ("idx_pesagens_otimizada",  "CREATE INDEX idx_pesagens_otimizada ON pesagens (animal_id, data_pesagem)"),
        ("idx_pesagens_max",        "CREATE INDEX idx_pesagens_max ON pesagens (animal_id, id DESC)"),
        ("idx_custos_busca",        "CREATE INDEX idx_custos_busca ON custos_operacionais (user_id, data_custo)"),
        ("idx_med_busca",           "CREATE INDEX idx_med_busca ON medicacoes (animal_id, data_aplicacao)"),
        ("idx_animais_venda",       "CREATE INDEX idx_animais_venda ON animais (user_id, data_venda)"),
        ("idx_animais_ativo",       "CREATE INDEX idx_animais_ativo ON animais (user_id, deleted_at)"),
        # Índices compostos para os padrões de query mais frequentes
        ("idx_animais_ativo_venda", "CREATE INDEX idx_animais_ativo_venda ON animais (user_id, deleted_at, data_venda)"),
        ("idx_animais_brinco",      "CREATE INDEX idx_animais_brinco ON animais (user_id, deleted_at, brinco)"),
        ("idx_sanitario_agenda",    "CREATE INDEX idx_sanitario_agenda ON protocolos_sanitarios (user_id, proxima_aplicacao, ativo)"),
        # FK sem índice automático no MySQL — adicionados para suportar JOINs e filtros
        ("idx_reproducao_vaca",     "CREATE INDEX idx_reproducao_vaca ON reproducao (vaca_id)"),
        ("idx_reproducao_user",     "CREATE INDEX idx_reproducao_user ON reproducao (user_id, data_parto_prevista)"),
        ("idx_estoque_mov_produto", "CREATE INDEX idx_estoque_mov_produto ON estoque_movimentacoes (produto_id, user_id)"),
        ("idx_modulos_pasto",       "CREATE INDEX idx_modulos_pasto ON modulos (pasto_id)"),
        ("idx_ocupacoes_modulo",    "CREATE INDEX idx_ocupacoes_modulo ON ocupacoes (modulo_id)"),
        ("idx_ocupacao_animais_oc", "CREATE INDEX idx_ocupacao_animais_oc ON ocupacao_animais (ocupacao_id)"),
        ("idx_animais_raca",        "CREATE INDEX idx_animais_raca ON animais (user_id, raca, deleted_at)"),
        # financial_schedule não tinha índice — cobre get_agendamentos e alertas de vencimento
        ("idx_financial_schedule_agenda", "CREATE INDEX idx_financial_schedule_agenda ON financial_schedule (user_id, deleted_at, vencimento)"),
        # animais(lote_id) sem índice — cobre JOIN em vw_resultado_lote e get_animais_por_lote
        ("idx_animais_lote",        "CREATE INDEX idx_animais_lote ON animais (lote_id, deleted_at)"),
        # inclui deleted_at para cobrir v_fluxo_caixa após condition pushdown do MySQL 8.0.22+
        ("idx_custos_user_del_data", "CREATE INDEX idx_custos_user_del_data ON custos_operacionais (user_id, deleted_at, data_custo)"),
    ]

    for nome_idx, sql in indices_sql:
        try:
            cursor.execute(sql)
            print(f"   -> Índice '{nome_idx}' verificado/criado.")
        except mysql.connector.Error as err:
            if err.errno == 1061:
                print(f"   -> Índice '{nome_idx}' já existe.")
            else:
                print(f"     Erro ao criar '{nome_idx}': {err}")

    # ==============================================================================
    # ETAPA 1.6: GESTÃO DE PASTOS
    # ==============================================================================
    print(" Criando tabelas de Gestão de Pastos...")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pastos (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        nome VARCHAR(100) NOT NULL,
        area_hectares DECIMAL(10,2),
        forrageira VARCHAR(100),
        capacidade_ua DECIMAL(10,2),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES usuarios(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS modulos (
        id INT AUTO_INCREMENT PRIMARY KEY,
        pasto_id INT NOT NULL,
        user_id INT NOT NULL,
        nome VARCHAR(100) NOT NULL,
        area_hectares DECIMAL(10,2),
        capacidade_ua DECIMAL(10,2),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (pasto_id) REFERENCES pastos(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES usuarios(id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ocupacoes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        modulo_id INT NOT NULL,
        user_id INT NOT NULL,
        data_entrada DATE NOT NULL,
        data_saida DATE NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (modulo_id) REFERENCES modulos(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES usuarios(id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ocupacao_animais (
        id INT AUTO_INCREMENT PRIMARY KEY,
        ocupacao_id INT NOT NULL,
        animal_id INT NOT NULL,
        FOREIGN KEY (ocupacao_id) REFERENCES ocupacoes(id) ON DELETE CASCADE,
        FOREIGN KEY (animal_id) REFERENCES animais(id) ON DELETE CASCADE
    );
    """)

    # ==============================================================================
    # ETAPA 1.7: HEREDITARIEDADE ANIMAL
    # ==============================================================================
    print(" Adicionando colunas de hereditariedade em 'animais'...")

    try:
        cursor.execute("ALTER TABLE animais ADD COLUMN pai_id INT NULL")
        cursor.execute("ALTER TABLE animais ADD CONSTRAINT fk_animais_pai FOREIGN KEY (pai_id) REFERENCES animais(id) ON DELETE SET NULL")
        print("   -> pai_id adicionado.")
    except mysql.connector.Error as err:
        if err.errno in (1060, 1061, 1826):
            print("   -> pai_id já existe.")
        else:
            print(f"   Alerta pai_id: {err}")

    try:
        cursor.execute("ALTER TABLE animais ADD COLUMN mae_id INT NULL")
        cursor.execute("ALTER TABLE animais ADD CONSTRAINT fk_animais_mae FOREIGN KEY (mae_id) REFERENCES animais(id) ON DELETE SET NULL")
        print("   -> mae_id adicionado.")
    except mysql.connector.Error as err:
        if err.errno in (1060, 1061, 1826):
            print("   -> mae_id já existe.")
        else:
            print(f"   Alerta mae_id: {err}")

    try:
        cursor.execute("ALTER TABLE animais ADD COLUMN raca VARCHAR(100) NULL AFTER sexo")
        print("   -> raca adicionada.")
    except mysql.connector.Error as err:
        if err.errno == 1060:
            print("   -> raca já existe.")
        else:
            print(f"   Alerta raca: {err}")

    try:
        cursor.execute("ALTER TABLE animais ADD COLUMN data_nascimento DATE NULL AFTER mae_id")
        print("   -> data_nascimento adicionada.")
    except mysql.connector.Error as err:
        if err.errno == 1060:
            print("   -> data_nascimento já existe.")
        else:
            print(f"   Alerta data_nascimento: {err}")

    try:
        cursor.execute("ALTER TABLE animais MODIFY COLUMN data_compra DATE NULL")
        print("   -> data_compra tornado nullable.")
    except mysql.connector.Error as err:
        print(f"   Alerta data_compra nullable: {err}")

    print(" Criando tabela 'reproducao'...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reproducao (
        id INT AUTO_INCREMENT PRIMARY KEY,
        vaca_id INT NOT NULL,
        touro_id INT NULL,
        touro_externo VARCHAR(200) NULL,
        data_cobertura DATE NOT NULL,
        data_parto DATE NULL,
        resultado ENUM('vivo','natimorto','aborto') NOT NULL,
        user_id INT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (vaca_id) REFERENCES animais(id) ON DELETE CASCADE,
        FOREIGN KEY (touro_id) REFERENCES animais(id) ON DELETE SET NULL,
        FOREIGN KEY (user_id) REFERENCES usuarios(id)
    );
    """)

    # ==============================================================================
    # ETAPA 5.3: DIAGNÓSTICO DE PRENHEZ — ALTER reproducao + view partos previstos
    # ==============================================================================
    print(" Adicionando colunas de diagnóstico em 'reproducao'...")
    for col, ddl in [
        ('diagnostico',       "ALTER TABLE reproducao ADD COLUMN diagnostico ENUM('pendente','positivo','negativo') DEFAULT 'pendente' AFTER data_cobertura"),
        ('data_diagnostico',  "ALTER TABLE reproducao ADD COLUMN data_diagnostico DATE NULL AFTER diagnostico"),
        ('data_parto_prevista',"ALTER TABLE reproducao ADD COLUMN data_parto_prevista DATE NULL AFTER data_diagnostico"),
    ]:
        try:
            cursor.execute(ddl)
            print(f"   -> Coluna '{col}' adicionada.")
        except mysql.connector.Error as err:
            if err.errno == 1060:
                print(f"   -> Coluna '{col}' já existe.")
            else:
                print(f"   Alerta '{col}': {err}")

    print(" Criando View vw_partos_previstos...")
    cursor.execute("""
    CREATE OR REPLACE VIEW vw_partos_previstos AS
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
      AND r.data_parto_prevista IS NOT NULL;
    """)

    # ==============================================================================
    # ETAPA 2: INTELIGÊNCIA DE DADOS
    # ==============================================================================

    # 2.1 View de GMD (Ganho Médio Diário)
    print(" [4/6] Atualizando View de Inteligência Zootécnica (GMD)...")
    cursor.execute("""
    CREATE OR REPLACE VIEW v_gmd_analitico AS
    WITH PesagensOrdenadas AS (
        SELECT
            animal_id, data_pesagem, peso,
            ROW_NUMBER() OVER(PARTITION BY animal_id ORDER BY data_pesagem ASC) as rn_asc,
            ROW_NUMBER() OVER(PARTITION BY animal_id ORDER BY data_pesagem DESC) as rn_desc
        FROM pesagens
        WHERE deleted_at IS NULL
    ),
    PrimeiraUltima AS (
        SELECT
            animal_id,
            MAX(CASE WHEN rn_asc = 1 THEN data_pesagem END) AS data_inicial,
            MAX(CASE WHEN rn_asc = 1 THEN peso END) AS peso_inicial,
            MAX(CASE WHEN rn_desc = 1 THEN data_pesagem END) AS data_final,
            MAX(CASE WHEN rn_desc = 1 THEN peso END) AS peso_final
        FROM PesagensOrdenadas
        GROUP BY animal_id
    )
    SELECT
        a.user_id, a.id as animal_id, a.brinco,
        p.peso_final,
        (p.peso_final - p.peso_inicial) as ganho_total,
        DATEDIFF(p.data_final, p.data_inicial) as dias,
        CASE
            WHEN DATEDIFF(p.data_final, p.data_inicial) > 0
            THEN (p.peso_final - p.peso_inicial) / DATEDIFF(p.data_final, p.data_inicial)
            ELSE 0
        END as gmd
    FROM PrimeiraUltima p
    JOIN animais a ON p.animal_id = a.id
    WHERE p.data_inicial <> p.data_final
      AND a.deleted_at IS NULL;
    """)

    # 2.1b Views de Gestão de Pastos
    print(" Criando Views de Gestão de Pastos...")

    cursor.execute("""
    CREATE OR REPLACE VIEW vw_ocupacao_atual AS
    SELECT
        m.id AS modulo_id,
        m.pasto_id,
        m.user_id,
        m.nome AS modulo_nome,
        m.capacidade_ua,
        o.id AS ocupacao_id,
        o.data_entrada,
        COUNT(oa.animal_id) AS ua_atual,
        ROUND(COUNT(oa.animal_id) / NULLIF(m.capacidade_ua, 0) * 100, 1) AS pct_lotacao
    FROM modulos m
    JOIN ocupacoes o ON o.modulo_id = m.id AND o.data_saida IS NULL
    JOIN ocupacao_animais oa ON oa.ocupacao_id = o.id
    GROUP BY m.id, m.pasto_id, m.user_id, m.nome, m.capacidade_ua, o.id, o.data_entrada;
    """)

    cursor.execute("""
    CREATE OR REPLACE VIEW vw_dias_descanso AS
    SELECT
        m.id AS modulo_id,
        m.pasto_id,
        m.user_id,
        m.nome AS modulo_nome,
        MAX(o.data_saida) AS ultima_saida,
        DATEDIFF(CURDATE(), MAX(o.data_saida)) AS dias_descanso
    FROM modulos m
    LEFT JOIN ocupacoes o ON o.modulo_id = m.id AND o.data_saida IS NOT NULL
    WHERE m.id NOT IN (SELECT modulo_id FROM ocupacoes WHERE data_saida IS NULL)
    GROUP BY m.id, m.pasto_id, m.user_id, m.nome;
    """)

    cursor.execute("""
    CREATE OR REPLACE VIEW vw_gmd_por_modulo AS
    SELECT
        o.modulo_id,
        m.nome AS modulo_nome,
        m.pasto_id,
        m.user_id,
        COUNT(DISTINCT oa.animal_id) AS qtd_animais,
        ROUND(AVG(g.gmd), 3) AS gmd_medio
    FROM ocupacoes o
    JOIN ocupacao_animais oa ON oa.ocupacao_id = o.id
    JOIN modulos m ON m.id = o.modulo_id
    LEFT JOIN v_gmd_analitico g ON g.animal_id = oa.animal_id
    GROUP BY o.modulo_id, m.nome, m.pasto_id, m.user_id;
    """)

    # 2.1c Views de Hereditariedade
    print(" Criando Views de Hereditariedade...")

    cursor.execute("""
    CREATE OR REPLACE VIEW vw_gmd_por_touro AS
    SELECT
        pai.id AS touro_id,
        pai.brinco AS touro_brinco,
        pai.raca AS touro_raca,
        pai.user_id,
        COUNT(DISTINCT filho.id) AS qtd_filhos,
        ROUND(AVG(g.gmd), 3) AS gmd_medio_filhos
    FROM animais pai
    JOIN animais filho ON filho.pai_id = pai.id AND filho.deleted_at IS NULL
    LEFT JOIN v_gmd_analitico g ON g.animal_id = filho.id
    WHERE pai.deleted_at IS NULL
    GROUP BY pai.id, pai.brinco, pai.raca, pai.user_id;
    """)

    cursor.execute("""
    CREATE OR REPLACE VIEW vw_historico_vaca AS
    SELECT
        r.vaca_id,
        a.user_id,
        COUNT(*) AS total_coberturas,
        SUM(CASE WHEN r.resultado = 'vivo' THEN 1 ELSE 0 END) AS partos_vivos,
        ROUND(SUM(CASE WHEN r.resultado = 'vivo' THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) AS taxa_sucesso,
        MIN(r.data_cobertura) AS primeira_cobertura,
        MAX(r.data_cobertura) AS ultima_cobertura
    FROM reproducao r
    JOIN animais a ON r.vaca_id = a.id
    GROUP BY r.vaca_id, a.user_id;
    """)

    # ==============================================================================
    # ETAPA 1.8: ESTOQUE VIRTUAL
    # ==============================================================================
    print(" Criando tabelas de Estoque Virtual...")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS estoque_produtos (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        nome VARCHAR(200) NOT NULL,
        unidade VARCHAR(50) NOT NULL,
        categoria ENUM('medicamento','vacina','suplemento','mineral','outro') NOT NULL DEFAULT 'outro',
        estoque_minimo DECIMAL(10,3) NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES usuarios(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS estoque_movimentacoes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        produto_id INT NOT NULL,
        tipo ENUM('entrada','saida') NOT NULL,
        quantidade DECIMAL(10,3) NOT NULL,
        custo_unitario DECIMAL(10,2) NULL,
        motivo VARCHAR(300) NULL,
        data_mov DATE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES usuarios(id),
        FOREIGN KEY (produto_id) REFERENCES estoque_produtos(id) ON DELETE CASCADE
    );
    """)

    # ==============================================================================
    # ETAPA 6.1: VALIDADE DE MEDICAMENTOS
    # ==============================================================================
    print(" Adicionando colunas de validade em 'estoque_movimentacoes'...")
    for col, ddl in [
        ('lote_fabricante', "ALTER TABLE estoque_movimentacoes ADD COLUMN lote_fabricante VARCHAR(100) NULL AFTER motivo"),
        ('data_validade',   "ALTER TABLE estoque_movimentacoes ADD COLUMN data_validade DATE NULL AFTER lote_fabricante"),
    ]:
        try:
            cursor.execute(ddl)
            print(f"   -> Coluna '{col}' adicionada.")
        except mysql.connector.Error as err:
            if err.errno == 1060:
                print(f"   -> Coluna '{col}' já existe.")
            else:
                print(f"   Alerta '{col}': {err}")

    # 2.1d View de Saldo de Estoque
    print(" Criando View vw_saldo_estoque...")
    cursor.execute("""
    CREATE OR REPLACE VIEW vw_saldo_estoque AS
    SELECT
        p.id AS produto_id,
        p.user_id,
        p.nome,
        p.unidade,
        p.categoria,
        p.estoque_minimo,
        COALESCE(SUM(CASE WHEN m.tipo = 'entrada' THEN m.quantidade ELSE 0 END), 0) AS total_entradas,
        COALESCE(SUM(CASE WHEN m.tipo = 'saida'   THEN m.quantidade ELSE 0 END), 0) AS total_saidas,
        COALESCE(SUM(CASE WHEN m.tipo = 'entrada' THEN m.quantidade ELSE -m.quantidade END), 0) AS saldo_atual,
        CASE
            WHEN COALESCE(SUM(CASE WHEN m.tipo = 'entrada' THEN m.quantidade ELSE -m.quantidade END), 0) < p.estoque_minimo
            THEN 1 ELSE 0
        END AS abaixo_minimo,
        MIN(CASE WHEN m.tipo = 'entrada' AND m.data_validade IS NOT NULL
                 THEN m.data_validade END)                              AS proxima_validade,
        CASE WHEN MIN(CASE WHEN m.tipo = 'entrada' AND m.data_validade IS NOT NULL
                           THEN m.data_validade END) < CURDATE()
             THEN 1 ELSE 0 END                                          AS tem_vencido
    FROM estoque_produtos p
    LEFT JOIN estoque_movimentacoes m ON m.produto_id = p.id
    GROUP BY p.id, p.user_id, p.nome, p.unidade, p.categoria, p.estoque_minimo;
    """)

    # ==============================================================================
    # ETAPA 1.9: AUTENTICAÇÃO — EMAIL E RESET DE SENHA
    # ==============================================================================
    print(" Adicionando coluna email em 'usuarios'...")
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN email VARCHAR(255) UNIQUE")
        print("   -> Coluna 'email' adicionada.")
    except mysql.connector.Error as err:
        if err.errno == 1060:
            print("   -> Coluna 'email' já existe.")
        else:
            print(f"   Alerta email: {err}")

    print(" Adicionando coluna created_at em 'usuarios'...")
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        print("   -> Coluna 'created_at' adicionada.")
    except mysql.connector.Error as err:
        if err.errno == 1060:
            print("   -> Coluna 'created_at' já existe.")
        else:
            print(f"   Alerta created_at: {err}")

    print(" Criando tabela 'password_reset_tokens'...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS password_reset_tokens (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        code CHAR(6) NOT NULL,
        expires_at DATETIME NOT NULL,
        used TINYINT(1) DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES usuarios(id) ON DELETE CASCADE
    );
    """)

    # 2.2 View Financeira (Fluxo de Caixa)
    print(" [5/6] Atualizando View de Inteligência Financeira (Fluxo de Caixa)...")
    cursor.execute("""
    CREATE OR REPLACE VIEW v_fluxo_caixa AS
    SELECT
        user_id,
        ano,
        SUM(receita) as total_entradas,
        SUM(despesa_compra) as total_compras,
        SUM(despesa_med) as total_med,
        SUM(despesa_ops) as total_ops
    FROM (
        SELECT user_id, YEAR(data_venda) as ano, preco_venda as receita, 0 as despesa_compra, 0 as despesa_med, 0 as despesa_ops
        FROM animais WHERE data_venda IS NOT NULL AND deleted_at IS NULL
        UNION ALL
        SELECT user_id, YEAR(data_compra) as ano, 0, preco_compra, 0, 0
        FROM animais WHERE deleted_at IS NULL AND data_compra IS NOT NULL
        UNION ALL
        SELECT a.user_id, YEAR(m.data_aplicacao) as ano, 0, 0, m.custo, 0
        FROM medicacoes m JOIN animais a ON m.animal_id = a.id WHERE m.deleted_at IS NULL AND a.deleted_at IS NULL
        UNION ALL
        SELECT user_id, YEAR(data_custo) as ano, 0, 0, 0, valor
        FROM custos_operacionais WHERE deleted_at IS NULL
    ) as uniao_geral
    GROUP BY user_id, ano;
    """)

    # ==============================================================================
    # ETAPA 5.2: CALENDÁRIO SANITÁRIO — PROTOCOLOS VACINAIS
    # ==============================================================================
    print(" Criando tabela 'protocolos_sanitarios'...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS protocolos_sanitarios (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        user_id         INT NOT NULL,
        nome            VARCHAR(200) NOT NULL,
        descricao       TEXT,
        intervalo_dias  INT NOT NULL,
        proxima_aplicacao DATE NOT NULL,
        ativo           TINYINT(1) DEFAULT 1,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES usuarios(id) ON DELETE CASCADE
    );
    """)

    # ==============================================================================
    # ETAPA 5.1: VIEW DE RESULTADO POR LOTE (P&L)
    # ==============================================================================
    print(" Criando View vw_resultado_lote...")
    cursor.execute("""
    CREATE OR REPLACE VIEW vw_resultado_lote AS
    SELECT
        l.id                                                          AS lote_id,
        l.user_id,
        l.codigo_lote,
        l.descricao,
        l.data_aquisicao,
        COUNT(a.id)                                                   AS total_animais,
        COALESCE(SUM(a.preco_compra), 0)                              AS custo_aquisicao,
        COALESCE(SUM(CASE WHEN a.data_venda IS NOT NULL
                          THEN a.preco_venda END), 0)                 AS receita_vendas,
        COALESCE(SUM(med.custo_med), 0)                               AS custo_medicacoes,
        COUNT(CASE WHEN a.data_venda IS NOT NULL THEN 1 END)          AS animais_vendidos,
        COALESCE(SUM(CASE WHEN a.data_venda IS NOT NULL
                          THEN a.preco_venda END), 0)
          - COALESCE(SUM(a.preco_compra), 0)
          - COALESCE(SUM(med.custo_med), 0)                           AS margem_bruta
    FROM lotes l
    JOIN animais a ON a.lote_id = l.id AND a.deleted_at IS NULL
    LEFT JOIN (
        SELECT animal_id, SUM(custo) AS custo_med
        FROM medicacoes
        WHERE deleted_at IS NULL
        GROUP BY animal_id
    ) med ON med.animal_id = a.id
    WHERE l.deleted_at IS NULL
    GROUP BY l.id, l.user_id, l.codigo_lote, l.descricao, l.data_aquisicao;
    """)


def main():
    print("\n---  INICIANDO SETUP COMPLETO DO BANCO DE DADOS ---")
    try:
        conn = _connect()
        cursor = conn.cursor()
        print(" Conexão estabelecida.")

        criar_schema(cursor)

        conn.commit()
        cursor.close()
        conn.close()
        print("\n [6/6] SUCESSO! ")
    except Exception as e:
        print(f"\n ERRO FATAL: {e}")
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
