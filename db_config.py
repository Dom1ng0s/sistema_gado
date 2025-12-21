import mysql.connector
from mysql.connector import pooling, Error
import os
from dotenv import load_dotenv
import logging
from contextlib import contextmanager

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("db_config")

load_dotenv()

db_settings = {
    "host": os.getenv('DB_HOST'),
    "user": os.getenv('DB_USER'),
    "password": os.getenv('DB_PASSWORD'),
    "database": os.getenv('DB_NAME'),
    "port": int(os.getenv('DB_PORT', 3306)),
    "autocommit": False,
    "connection_timeout": 10
}

connection_pool = None

try:
    connection_pool = mysql.connector.pooling.MySQLConnectionPool(
        pool_name="gado_pool", pool_size=5, **db_settings
    )
    logger.info("✅ Modo Rápido (Pool) ativado!")
except Error as e:
    logger.warning(f"⚠️ AVISO: Falha ao criar Pool: {e}")
    connection_pool = None

def get_db_connection():
    try:
        if connection_pool:
            return connection_pool.get_connection()
        return mysql.connector.connect(**db_settings)
    except Error as e:
        logger.error(f"❌ ERRO CRÍTICO DE CONEXÃO: {e}")
        return None

def close_db_connection(connection):
    if connection and connection.is_connected():
        connection.close()

@contextmanager
def get_db_cursor():
    conn = get_db_connection()
    if conn is None:
        raise ConnectionError("Falha na conexão com BD")
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        close_db_connection(conn)