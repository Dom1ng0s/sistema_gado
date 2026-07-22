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
              -- expires_at é gravado em UTC (datetime.now(timezone.utc) em auth.py);
              -- NOW() usa o fuso da sessão do servidor e deslocaria a janela — ver #59.
              AND t.expires_at > UTC_TIMESTAMP()
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


def delete_user_and_data(user_id):
    """Apaga o tenant inteiro em uma única transação, na ordem de dependência.

    A maioria das FKs para usuarios(id) é RESTRICT (sem ON DELETE CASCADE),
    então um DELETE direto em usuarios falha (errno 1451) se houver qualquer
    dado. Removemos os filhos primeiro. Tabelas com CASCADE a partir de
    usuarios (pastos, estoque_produtos, protocolos_sanitarios,
    password_reset_tokens) e a partir de animais (ocupacao_animais) somem
    junto — mas as intermediárias com user_id RESTRICT (modulos, ocupacoes,
    estoque_movimentacoes, reproducao) precisam ser apagadas explicitamente.
    """
    # Ordem: netos → filhos → tabelas diretas de usuarios → usuarios.
    comandos = [
        # filhos de animais que bloqueiam o DELETE de animais (RESTRICT)
        "DELETE p FROM pesagens p JOIN animais a ON p.animal_id = a.id WHERE a.user_id = %s",
        "DELETE m FROM medicacoes m JOIN animais a ON m.animal_id = a.id WHERE a.user_id = %s",
        "DELETE FROM reproducao WHERE user_id = %s",
        # cadeia de pastos (ocupacao_animais cascateia de ocupacoes)
        "DELETE FROM ocupacoes WHERE user_id = %s",
        "DELETE FROM modulos WHERE user_id = %s",
        "DELETE FROM pastos WHERE user_id = %s",
        # animais antes de lotes (animais.lote_id é RESTRICT)
        "DELETE FROM animais WHERE user_id = %s",
        "DELETE FROM lotes WHERE user_id = %s",
        # estoque
        "DELETE FROM estoque_movimentacoes WHERE user_id = %s",
        "DELETE FROM estoque_produtos WHERE user_id = %s",
        # tabelas diretas de usuarios
        "DELETE FROM custos_operacionais WHERE user_id = %s",
        "DELETE FROM configuracoes WHERE user_id = %s",
        "DELETE FROM financial_schedule WHERE user_id = %s",
        "DELETE FROM protocolos_sanitarios WHERE user_id = %s",
        "DELETE FROM password_reset_tokens WHERE user_id = %s",
        "DELETE FROM usuarios WHERE id = %s",
    ]
    with get_db_cursor() as cursor:
        for sql in comandos:
            cursor.execute(sql, (user_id,))
