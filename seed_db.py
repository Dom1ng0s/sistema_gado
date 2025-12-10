import mysql.connector
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
from datetime import date, timedelta
import random

# Carrega variáveis
load_dotenv()

print("\n--- ⚖️ AJUSTANDO DEMO: GMD REALISTA (0.5 - 0.8 kg/dia) ---")

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

    # 2. Configura Usuário "demo"
    username = "demo"
    senha_plain = "demo123"
    
    cursor.execute("SELECT id FROM usuarios WHERE username = %s", (username,))
    res = cursor.fetchone()
    
    if res:
        user_id = res[0]
        print(f"♻️  Limpando dados antigos de '{username}'...")
        cursor.execute("DELETE FROM custos_operacionais WHERE user_id = %s", (user_id,))
        cursor.execute("SELECT id FROM animais WHERE user_id = %s", (user_id,))
        animais = cursor.fetchall()
        for (aid,) in animais:
            cursor.execute("DELETE FROM pesagens WHERE animal_id = %s", (aid,))
            cursor.execute("DELETE FROM medicacoes WHERE animal_id = %s", (aid,))
        cursor.execute("DELETE FROM animais WHERE user_id = %s", (user_id,))
    else:
        print(f"👤 Criando usuário '{username}'...")
        hash_senha = generate_password_hash(senha_plain)
        cursor.execute("INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)", (username, hash_senha))
        user_id = cursor.lastrowid

    hoje = date.today()

    # ==============================================================================
    # PARÂMETROS ECONÔMICOS & ZOOTÉCNICOS
    # ==============================================================================
    PRECO_COMPRA_ARROBA = 240.00
    PRECO_VENDA_ARROBA = 295.00
    
    # GMD Alvo: Entre 0.500 e 0.800 kg/dia
    # Peso Entrada: ~270kg (9@) | Peso Saída: ~510kg (17@) | Ganho: 240kg
    # Tempo Necessário: 240kg / 0.6 = ~400 dias (Ciclo Longo a Pasto)
    
    PESO_ENTRADA_REF = list(range(260, 290, 10)) # 260, 270, 280
    PESO_SAIDA_REF = list(range(500, 540, 10))   # 500 a 530

    # ==============================================================================
    # HISTÓRICO: 3 LOTES VENDIDOS (COM GMD REALISTA)
    # ==============================================================================
    
    # Ciclo 1: Vendido há 2 anos
    print("📈 [1/4] Gerando Ciclo 1 (2023)...")
    dias_ciclo = 400 # Tempo para engordar a pasto
    dt_venda_c1 = hoje - timedelta(days=730)
    dt_compra_c1 = dt_venda_c1 - timedelta(days=dias_ciclo)
    
    for i in range(1, 21):
        brinco = f"L1-{i:02d}"
        p_in = random.choice(PESO_ENTRADA_REF)
        
        # Gera um GMD aleatório para este animal e calcula peso final
        gmd_hist = random.uniform(0.5, 0.8)
        p_out = p_in + (gmd_hist * dias_ciclo)
        
        v_compra = (p_in / 30) * PRECO_COMPRA_ARROBA
        v_venda = (p_out / 30) * PRECO_VENDA_ARROBA

        cursor.execute("""
            INSERT INTO animais (brinco, sexo, data_compra, preco_compra, data_venda, preco_venda, user_id)
            VALUES (%s, 'M', %s, %s, %s, %s, %s)
        """, (brinco, dt_compra_c1, v_compra, dt_venda_c1, v_venda, user_id))
        aid = cursor.lastrowid
        
        # Pesagens
        cursor.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", (aid, dt_compra_c1, p_in))
        # Pesagem intermediária para dar "corpo" ao gráfico
        dt_meio = dt_compra_c1 + timedelta(days=200)
        p_meio = p_in + (gmd_hist * 200)
        cursor.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", (aid, dt_meio, p_meio))
        cursor.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", (aid, dt_venda_c1, p_out))

    # Ciclo 2: Vendido há 1 ano
    print("📈 [2/4] Gerando Ciclo 2 (2024)...")
    dt_venda_c2 = hoje - timedelta(days=365)
    dt_compra_c2 = dt_venda_c2 - timedelta(days=dias_ciclo)
    
    for i in range(1, 21):
        brinco = f"L2-{i:02d}"
        p_in = random.choice(PESO_ENTRADA_REF)
        gmd_hist = random.uniform(0.5, 0.8)
        p_out = p_in + (gmd_hist * dias_ciclo)
        
        v_compra = (p_in / 30) * PRECO_COMPRA_ARROBA
        v_venda = (p_out / 30) * PRECO_VENDA_ARROBA

        cursor.execute("""
            INSERT INTO animais (brinco, sexo, data_compra, preco_compra, data_venda, preco_venda, user_id)
            VALUES (%s, 'M', %s, %s, %s, %s, %s)
        """, (brinco, dt_compra_c2, v_compra, dt_venda_c2, v_venda, user_id))
        aid = cursor.lastrowid
        cursor.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", (aid, dt_compra_c2, p_in))
        cursor.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", (aid, dt_venda_c2, p_out))

    # Ciclo 3: Venda Recente
    print("📈 [3/4] Gerando Vendas Recentes...")
    dt_venda_c3 = hoje - timedelta(days=5)
    dt_compra_c3 = dt_venda_c3 - timedelta(days=dias_ciclo)
    
    for i in range(1, 21):
        brinco = f"L3-{i:02d}"
        p_in = random.choice(PESO_ENTRADA_REF)
        gmd_hist = random.uniform(0.5, 0.8)
        p_out = p_in + (gmd_hist * dias_ciclo)
        
        v_compra = (p_in / 30) * PRECO_COMPRA_ARROBA
        v_venda = (p_out / 30) * PRECO_VENDA_ARROBA

        cursor.execute("""
            INSERT INTO animais (brinco, sexo, data_compra, preco_compra, data_venda, preco_venda, user_id)
            VALUES (%s, 'M', %s, %s, %s, %s, %s)
        """, (brinco, dt_compra_c3, v_compra, dt_venda_c3, v_venda, user_id))
        aid = cursor.lastrowid
        cursor.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", (aid, dt_compra_c3, p_in))
        cursor.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", (aid, dt_venda_c3, p_out))

    # ==============================================================================
    # ATUAIS: ESTOQUE NO PASTO (COM 2 PESAGENS E GMD CONTROLADO)
    # ==============================================================================
    print("🐂 [4/4] Povoando Estoque Atual (GMD 0.5 a 0.8)...")
    
    # Comprados há 120 dias
    dias_pasto = 120
    dt_compra_atual = hoje - timedelta(days=dias_pasto)
    
    for i in range(1, 16): # 15 Animais
        brinco = f"A-{i:02d}"
        p_inicial = random.choice(PESO_ENTRADA_REF)
        v_compra = (p_inicial / 30) * 260.00 # Compra recente um pouco mais cara
        
        # INSERE ANIMAL
        cursor.execute("""
            INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id)
            VALUES (%s, 'M', %s, %s, %s)
        """, (brinco, dt_compra_atual, v_compra, user_id))
        aid = cursor.lastrowid
        
        # PESAGEM 1: NA COMPRA
        cursor.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", 
                       (aid, dt_compra_atual, p_inicial))
        
        # PESAGEM 2: HOJE (Com GMD controlado)
        # Sorteia GMD alvo entre 0.5 e 0.8
        gmd_alvo = random.uniform(0.5, 0.8)
        peso_atual = p_inicial + (gmd_alvo * dias_pasto)
        
        cursor.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", 
                       (aid, hoje, peso_atual))

    # ==============================================================================
    # CUSTOS OPERACIONAIS (Para manter o lucro visível)
    # ==============================================================================
    print("💸 Lançando Custos...")
    cursor_date = hoje - timedelta(days=1100)
    while cursor_date <= hoje:
        dt_lanc = cursor_date.replace(day=10)
        if dt_lanc > hoje: break
        
        cursor.execute("INSERT INTO custos_operacionais (user_id, categoria, tipo_custo, valor, data_custo, descricao) VALUES (%s, 'Fixo', 'Salário', 2000.00, %s, 'Mão de Obra')", (user_id, dt_lanc))
        cursor.execute("INSERT INTO custos_operacionais (user_id, categoria, tipo_custo, valor, data_custo, descricao) VALUES (%s, 'Fixo', 'Nutrição', 600.00, %s, 'Sal Mineral')", (user_id, dt_lanc))
        cursor_date += timedelta(days=30)

    conn.commit()
    cursor.close()
    conn.close()
    print("\n✅ [SUCESSO] Demo Atualizada com GMD Realista!")
    print(f"👉 Acesse: {username} / {senha_plain}")
    print("👉 Confira a ficha de qualquer animal 'A-XX' para ver o GMD entre 0.5 e 0.8.")

except Exception as e:
    print(f"\n❌ ERRO: {e}")