from flask_login import UserMixin
from db_config import get_db_cursor


class User(UserMixin):
    def __init__(self, id, username, password_hash, email=None):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.email = email

    @staticmethod
    def get_user_id(user_id):
        # Flask-Login serializa o id como string na sessão; o Postgres não
        # coage text→integer implicitamente como o MySQL fazia.
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            return None
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT id, username, password_hash, email FROM usuarios WHERE id = %s",
                (uid,),
            )
            dados = cursor.fetchone()
        if dados:
            return User(dados[0], dados[1], dados[2], dados[3])
        return None
