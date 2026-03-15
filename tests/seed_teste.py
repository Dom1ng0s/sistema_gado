import mysql.connector
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
from datetime import date, timedelta
import random

load_dotenv()

try:
    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        port=int(os.getenv('DB_PORT', 3306))
    )
    cursor = conn.cursor()

    username = "teste"
    senha_plain = "teste123"
    QTD_ANIMAIS = 500

    cursor.execute("SELECT id FROM usuarios WHERE username = %s", (username,))
    res = cursor.fetchone()

    if res:
        user_id = res[0]
        cursor.execute("DELETE FROM pesagens WHERE animal_id IN (SELECT id FROM animais WHERE user_id = %s)", (user_id,))
        cursor.execute("DELETE FROM custos_operacionais WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM animais WHERE user_id = %s", (user_id,))
    else:
        hash_senha = generate_password_hash(senha_plain)
        cursor.execute("INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)", (username, hash_senha))
        user_id = cursor.lastrowid

    data_inicio = date.today() - timedelta(days=730)

    # 1. Animais com preços reais
    animais_data = []
    for i in range(1, QTD_ANIMAIS + 1):
        brinco = f"NELORE-{i:04d}"
        sexo = random.choice(['M', 'F'])
        dias_compra = random.randint(0, 700)
        data_compra = data_inicio + timedelta(days=dias_compra)
        preco_compra = round(random.uniform(1500.0, 3000.0), 2)
        animais_data.append((brinco, sexo, data_compra, preco_compra, user_id))

    cursor.executemany(
        "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id) VALUES (%s, %s, %s, %s, %s)",
        animais_data
    )

    cursor.execute("SELECT id, data_compra FROM animais WHERE user_id = %s", (user_id,))
    animais_inseridos = cursor.fetchall()

    # 2. Pesagens com curva de crescimento zootécnico real
    pesagens_data = []
    for animal_id, data_compra in animais_inseridos:
        peso_atual = round(random.uniform(180.0, 220.0), 2)
        data_pesagem = data_compra
        
        num_pesagens = random.randint(3, 6)
        for _ in range(num_pesagens):
            pesagens_data.append((animal_id, data_pesagem, peso_atual))
            dias_intervalo = random.randint(60, 120)
            data_pesagem += timedelta(days=dias_intervalo)
            
            if data_pesagem > date.today():
                break
                
            peso_atual += round(dias_intervalo * random.uniform(0.5, 0.9), 2)

    cursor.executemany(
        "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)",
        pesagens_data
    )

    # 3. Custos operacionais para visualização de dashboard
    custos_data = []
    categorias = ['Alimentação', 'Mão de Obra', 'Impostos', 'Manutenção', 'Combustível']
    for i in range(120):
        data_custo = data_inicio + timedelta(days=random.randint(0, 700))
        categoria = random.choice(categorias)
        valor = round(random.uniform(150.0, 5000.0), 2)
        custos_data.append((user_id, data_custo, 'Fixos', categoria, valor, 'Custo gerado para teste analítico'))

    cursor.executemany(
        "INSERT INTO custos_operacionais (user_id, data_custo, tipo_custo, categoria, valor, descricao) VALUES (%s, %s, %s, %s, %s, %s)",
        custos_data
    )

    conn.commit()
    cursor.close()
    conn.close()

except Exception as e:
    print(f"Erro na execução: {e}")