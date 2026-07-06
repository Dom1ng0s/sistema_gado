from db_config import get_db_cursor
from datetime import timedelta, date, datetime


def insert_reproducao(user_id, vaca_id, touro_id, touro_externo, data_cobertura, data_parto, resultado):
    if isinstance(data_cobertura, str):
        data_cobertura_obj = datetime.strptime(data_cobertura, '%Y-%m-%d').date()
    else:
        data_cobertura_obj = data_cobertura

    data_parto_prevista = data_cobertura_obj + timedelta(days=285)

    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO reproducao "
            "(user_id, vaca_id, touro_id, touro_externo, data_cobertura, "
            " data_parto, resultado, data_parto_prevista) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (user_id, vaca_id, touro_id or None, touro_externo or None,
             data_cobertura, data_parto or None, resultado,
             data_parto_prevista)
        )
        return cursor.lastrowid


def get_reproducao_by_vaca(vaca_id, user_id):
    """Eventos reprodutivos da vaca incluindo diagnóstico e data prevista de parto."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT r.id, r.data_cobertura, r.data_parto, r.resultado, "
            "    t.brinco AS touro_brinco, r.touro_externo, "
            "    r.diagnostico, r.data_diagnostico, r.data_parto_prevista "
            "FROM reproducao r "
            "JOIN animais v ON r.vaca_id = v.id "
            "LEFT JOIN animais t ON r.touro_id = t.id "
            "WHERE r.vaca_id = %s AND v.user_id = %s "
            "ORDER BY r.data_cobertura DESC",
            (vaca_id, user_id)
        )
        return cursor.fetchall()


def update_diagnostico(reproducao_id, user_id, diagnostico, data_diagnostico):
    """Registra resultado do DG. Retorna True se encontrado e atualizado."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "UPDATE reproducao r "
            "JOIN animais v ON r.vaca_id = v.id AND v.user_id = %s "
            "SET r.diagnostico = %s, r.data_diagnostico = %s "
            "WHERE r.id = %s",
            (user_id, diagnostico, data_diagnostico or None, reproducao_id)
        )
        return cursor.rowcount > 0


def get_partos_previstos(user_id, dias=30):
    """Vacas com DG positivo e parto previsto nos próximos `dias` dias."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id, vaca_brinco, data_cobertura, data_parto_prevista, dias_restantes "
            "FROM vw_partos_previstos "
            "WHERE user_id = %s AND dias_restantes <= %s "
            "ORDER BY dias_restantes ASC",
            (user_id, dias)
        )
        return cursor.fetchall()


def get_vaca_id_by_reproducao(reproducao_id, user_id):
    """Retorna o vaca_id da reprodução informada, validando dono via JOIN. None se não encontrado."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT r.vaca_id FROM reproducao r "
            "JOIN animais v ON r.vaca_id = v.id "
            "WHERE r.id = %s AND v.user_id = %s",
            (reproducao_id, user_id)
        )
        row = cursor.fetchone()
        return row[0] if row else None


def get_contagem_gestantes(user_id):
    """Retorna o número de vacas com DG positivo e parto ainda não registrado."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM reproducao r "
            "JOIN animais v ON r.vaca_id = v.id "
            "WHERE v.user_id = %s AND r.diagnostico = 'positivo' "
            "AND r.data_parto IS NULL AND v.deleted_at IS NULL",
            (user_id,)
        )
        return cursor.fetchone()[0]
