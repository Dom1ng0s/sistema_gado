import mysql.connector
import os
from dotenv import load_dotenv

# Carrega as senhas do arquivo .env
load_dotenv()

print("Conectando ao banco de dados...")

try:
    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        port=int(os.getenv('DB_PORT', 3306))
    )
    cursor = conn.cursor()

    # 1. Cria a tabela de usuários
    print("Criando tabela 'usuarios'...")
    sql_create = """
    CREATE TABLE IF NOT EXISTS usuarios (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL
    );
    """
    cursor.execute(sql_create)
    print("✅ Tabela 'usuarios' verificada/criada.")

    # 2. Insere o usuário ADMIN (se não existir)
    print("Verificando usuário admin...")
    # Hash para senha 'admin123'
    hash_senha = 'scrypt:32768:8:1$kXp5C5q9Zz8s$6e28d45f348043653131707572706854199c07172551061919864273347072557766858172970635489708764835940561570198038755030800008853755355'
    
    # Tenta inserir. Se der erro de duplicidade (já existe), o except captura.
    try:
        sql_insert = "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)"
        cursor.execute(sql_insert, ('admin', hash_senha))
        conn.commit()
        print("✅ Usuário 'admin' criado com sucesso!")
    except mysql.connector.Error as err:
        if err.errno == 1062: # Código de erro para Duplicidade
            print("ℹ️ Usuário 'admin' já existe. Nenhuma ação necessária.")
        else:
            print(f"⚠️ Erro ao inserir usuário: {err}")

    cursor.close()
    conn.close()
    print("\n--- CONFIGURAÇÃO CONCLUÍDA ---")

except Exception as e:
    print(f"\n❌ ERRO CRÍTICO: {e}")
    print("Verifique se o seu arquivo .env está correto.")