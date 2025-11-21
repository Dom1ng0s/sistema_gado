import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

def get_db_connection():
    
    connection = None
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        # Garante que inserções (INSERT) sejam salvas automaticamente
        connection.autocommit = True 
    except Error as e:
        print(f"ERRO DE CONEXÃO: {e}")
    
    return connection

def close_db_connection(connection):
    """Fecha a conexão se estiver aberta."""
    if connection and connection.is_connected():
        connection.close()