import mysql.connector
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

# Carrega configurações
load_dotenv()

try:
    print("Conectando ao banco...")
    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        port=int(os.getenv('DB_PORT', 3306))
    )
    cursor = conn.cursor()

    # 1. Gera um hash compatível com SEU sistema
    nova_senha = 'admin123'
    novo_hash = generate_password_hash(nova_senha)
    
    print(f"Gerando novo hash para a senha: {nova_senha}")

    # 2. Atualiza o usuário 'admin' existente
    sql = "UPDATE usuarios SET password_hash = %s WHERE username = 'admin'"
    cursor.execute(sql, (novo_hash,))
    conn.commit()

    if cursor.rowcount > 0:
        print("✅ Sucesso! A senha do usuário 'admin' foi redefinida para 'admin123'.")
    else:
        # Se não atualizou nada, é porque o usuário admin não existia. Vamos criar.
        print("Usuário 'admin' não encontrado. Criando novo...")
        sql_insert = "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)"
        cursor.execute(sql_insert, ('admin', novo_hash))
        conn.commit()
        print("✅ Usuário 'admin' criado com a senha 'admin123'.")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"❌ Erro: {e}")