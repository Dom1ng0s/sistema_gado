import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

try:
    print("Conectando ao banco...")
    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )
    cursor = conn.cursor()

    print("🔧 Ajustando regras de duplicidade...")

    # Tenta remover o índice antigo (pode falhar se o nome for diferente, então usamos try/except)
    try:
        cursor.execute("DROP INDEX brinco ON animais")
        print("✅ Índice antigo 'brinco' removido.")
    except Exception as e:
        print(f"⚠️ Aviso: Não foi possível remover índice 'brinco' (talvez já não exista ou tenha outro nome). Erro: {e}")

    # Cria o novo índice composto
    try:
        sql = "ALTER TABLE animais ADD UNIQUE INDEX idx_brinco_usuario (brinco, user_id)"
        cursor.execute(sql)
        print("✅ Nova regra aplicada: (Brinco + Usuário) agora é a chave única.")
    except Exception as e:
        print(f"⚠️ Erro ao criar novo índice: {e}")

    conn.commit()
    cursor.close()
    conn.close()
    print("\nFim do ajuste.")

except Exception as e:
    print(f"❌ Erro de Conexão: {e}")