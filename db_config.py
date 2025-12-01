import mysql.connector
from mysql.connector import pooling, Error
import os
from dotenv import load_dotenv

load_dotenv()

# Configuração Centralizada
db_settings = {
    "host": os.getenv('DB_HOST'),
    "user": os.getenv('DB_USER'),
    "password": os.getenv('DB_PASSWORD'),
    "database": os.getenv('DB_NAME'),
    "port": int(os.getenv('DB_PORT', 3306)),
    "autocommit": False, # IMPORTANTE: Desabilitar autocommit para gerenciar transações no context manager
    "connection_timeout": 10
}

connection_pool = None

print("--- INICIANDO CONEXÃO COM O BANCO ---")
try:
    # Tenta criar o Pool (Modo Rápido)
    connection_pool = mysql.connector.pooling.MySQLConnectionPool(
        pool_name="gado_pool",
        pool_size=5,
        **db_settings
    )
    print("✅ Modo Rápido (Pool) ativado!")
except Error as e:
    print(f"⚠️ AVISO: Falha ao criar Pool. Usando modo de segurança.")
    print(f"   Motivo: {e}")
    connection_pool = None

def get_db_connection():
    """Tenta pegar do pool, se falhar, cria conexão direta."""
    try:
        if connection_pool:
            return connection_pool.get_connection()
        else:
            # Fallback: Se o pool não existe, conecta direto (Modo Lento mas Seguro)
            return mysql.connector.connect(**db_settings)
    except Error as e:
        print(f"❌ ERRO CRÍTICO DE CONEXÃO: {e}")
        return None

def close_db_connection(connection):
    """Fecha ou devolve a conexão."""
    if connection and connection.is_connected():
        connection.close()
