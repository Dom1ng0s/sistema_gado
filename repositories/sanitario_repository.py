from db_config import get_db_cursor


def get_protocolos(user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id, nome, descricao, intervalo_dias, proxima_aplicacao, ativo "
            "FROM protocolos_sanitarios "
            "WHERE user_id = %s AND ativo = 1 "
            "ORDER BY proxima_aplicacao ASC",
            (user_id,)
        )
        return cursor.fetchall()


def insert_protocolo(user_id, nome, descricao, intervalo_dias, proxima_aplicacao):
    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO protocolos_sanitarios "
            "(user_id, nome, descricao, intervalo_dias, proxima_aplicacao) "
            "VALUES (%s, %s, %s, %s, %s)",
            (user_id, nome, descricao or None, intervalo_dias, proxima_aplicacao)
        )
        return cursor.lastrowid


def get_vencendo_em_dias(user_id, dias=7):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id, nome, proxima_aplicacao, intervalo_dias "
            "FROM protocolos_sanitarios "
            "WHERE user_id = %s AND ativo = 1 "
            "AND proxima_aplicacao <= DATE_ADD(CURDATE(), INTERVAL %s DAY) "
            "ORDER BY proxima_aplicacao ASC",
            (user_id, dias)
        )
        return cursor.fetchall()


def registrar_aplicacao(protocolo_id, user_id):
    """Avança proxima_aplicacao em +intervalo_dias. Retorna nome do protocolo ou None se não encontrado."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT nome FROM protocolos_sanitarios "
            "WHERE id = %s AND user_id = %s AND ativo = 1",
            (protocolo_id, user_id)
        )
        row = cursor.fetchone()
        if not row:
            return None
        nome = row[0]
        cursor.execute(
            "UPDATE protocolos_sanitarios "
            "SET proxima_aplicacao = DATE_ADD(proxima_aplicacao, INTERVAL intervalo_dias DAY) "
            "WHERE id = %s",
            (protocolo_id,)
        )
        return nome


def desativar_protocolo(protocolo_id, user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "UPDATE protocolos_sanitarios SET ativo = 0 "
            "WHERE id = %s AND user_id = %s",
            (protocolo_id, user_id)
        )
