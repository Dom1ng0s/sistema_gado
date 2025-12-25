import mysql.connector
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

print("\n--- 🚀 INICIANDO SETUP COMPLETO DO BANCO DE DADOS (COM SOFT DELETE) ---")

try:
    # 1. Conexão
    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        port=int(os.getenv('DB_PORT', 3306))
    )
    cursor = conn.cursor()
    print("✅ Conexão estabelecida.")

    # ==============================================================================
    # ETAPA 1: TABELAS FUNDAMENTAIS (Ordem de Dependência: Usuários -> Outros)
    # ==============================================================================
    
    # 1.1 Tabela USUÁRIOS
    print("🔨 [1/6] Criando tabela 'usuarios'...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL
    );
    """)

    # 1.2 Inserção do ADMIN Padrão
    print("👤 Verificando usuário 'admin'...")
    hash_admin = 'scrypt:32768:8:1$kXp5C5q9Zz8s$6e28d45f348043653131707572706854199c07172551061919864273347072557766858172970635489708764835940561570198038755030800008853755355'
    try:
        cursor.execute("INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)", ('admin', hash_admin))
        print("   -> Usuário 'admin' criado (Senha: admin123).")
    except mysql.connector.Error as err:
        if err.errno == 1062:
            print("   -> Usuário 'admin' já existe.")
        else:
            raise err

    # 1.3 Tabela ANIMAIS (Atualizada com deleted_at)
    print("🔨 [2/6] Criando tabela 'animais'...")
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

    # 1.4 Tabelas Satélites (Atualizadas com deleted_at)
    print("🔨 [3/6] Criando tabelas satélites (pesagens, medicacoes, custos)...")
    
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

    # ==============================================================================
    # ETAPA 1.5: ÍNDICES DE PERFORMANCE (OTIMIZAÇÃO)
    # ==============================================================================
    print("🚀 [Extra] Aplicando índices de performance...")
    
    indices_sql = [
        ("idx_pesagens_otimizada", "CREATE INDEX idx_pesagens_otimizada ON pesagens (animal_id, data_pesagem)"),
        ("idx_pesagens_max", "CREATE INDEX idx_pesagens_max ON pesagens (animal_id, id DESC)"),
        ("idx_custos_busca", "CREATE INDEX idx_custos_busca ON custos_operacionais (user_id, data_custo)"),
        ("idx_med_busca", "CREATE INDEX idx_med_busca ON medicacoes (animal_id, data_aplicacao)"),
        ("idx_animais_venda", "CREATE INDEX idx_animais_venda ON animais (user_id, data_venda)"),
        # NOVO ÍNDICE PARA SOFT DELETE
        ("idx_animais_ativo", "CREATE INDEX idx_animais_ativo ON animais (user_id, deleted_at)")
    ]

    for nome_idx, sql in indices_sql:
        try:
            cursor.execute(sql)
            print(f"   -> Índice '{nome_idx}' verificado/criado.")
        except mysql.connector.Error as err:
            if err.errno == 1061:  # Duplicate key name
                print(f"   -> Índice '{nome_idx}' já existe.")
            else:
                print(f"   ⚠️  Erro ao criar '{nome_idx}': {err}")

    # ==============================================================================
    # ETAPA 2: INTELIGÊNCIA DE DADOS (VIEWS ATUALIZADAS PARA SOFT DELETE)
    # ==============================================================================

    # 2.1 View de GMD (Ganho Médio Diário)
    print("🧠 [4/6] Atualizando View de Inteligência Zootécnica (GMD)...")
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

    # 2.2 View Financeira (Fluxo de Caixa)
    print("🧠 [5/6] Atualizando View de Inteligência Financeira (Fluxo de Caixa)...")
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
        FROM animais WHERE deleted_at IS NULL
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
    # CONCLUSÃO
    # ==============================================================================
    conn.commit()
    cursor.close()
    conn.close()
    print("\n✅ [6/6] SUCESSO! Banco de dados atualizado para SOFT DELETE.")

except Exception as e:
    print(f"\n❌ ERRO FATAL: {e}")