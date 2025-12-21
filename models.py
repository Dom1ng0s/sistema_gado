from flask_login import UserMixin
from db_config import get_db_connection, close_db_connection

class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

    @staticmethod
    def get_user_id(user_id):
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT id, username, password_hash FROM usuarios WHERE id = %s", (user_id,))
                dados = cursor.fetchone()
                if dados:
                    return User(dados[0], dados[1], dados[2])
            finally:
                close_db_connection(conn)
        return None