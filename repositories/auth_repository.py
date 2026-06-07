from db_config import get_db_cursor


def get_user_by_email(email):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id, username, password_hash, email FROM usuarios WHERE email = %s",
            (email,)
        )
        return cursor.fetchone()


def set_user_email(user_id, email):
    with get_db_cursor() as cursor:
        cursor.execute(
            "UPDATE usuarios SET email = %s WHERE id = %s",
            (email, user_id)
        )


def save_reset_token(user_id, code, expires_at):
    with get_db_cursor() as cursor:
        cursor.execute(
            "UPDATE password_reset_tokens SET used = 1 WHERE user_id = %s AND used = 0",
            (user_id,)
        )
        cursor.execute(
            "INSERT INTO password_reset_tokens (user_id, code, expires_at) VALUES (%s, %s, %s)",
            (user_id, code, expires_at)
        )


def get_valid_token(email, code):
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT t.id, t.user_id
            FROM password_reset_tokens t
            JOIN usuarios u ON u.id = t.user_id
            WHERE u.email = %s
              AND t.code = %s
              AND t.used = 0
              AND t.expires_at > NOW()
        """, (email, code))
        return cursor.fetchone()


def mark_token_used(token_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "UPDATE password_reset_tokens SET used = 1 WHERE id = %s",
            (token_id,)
        )


def update_password(user_id, new_hash):
    with get_db_cursor() as cursor:
        cursor.execute(
            "UPDATE usuarios SET password_hash = %s WHERE id = %s",
            (new_hash, user_id)
        )
