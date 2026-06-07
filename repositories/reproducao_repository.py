from db_config import get_db_cursor


def insert_reproducao(user_id, vaca_id, touro_id, touro_externo, data_cobertura, data_parto, resultado):
    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO reproducao "
            "(user_id, vaca_id, touro_id, touro_externo, data_cobertura, data_parto, resultado) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (user_id, vaca_id, touro_id or None, touro_externo or None,
             data_cobertura, data_parto or None, resultado)
        )
        return cursor.lastrowid


def get_reproducao_by_vaca(vaca_id, user_id):
    """Eventos reprodutivos da vaca com nome do touro (interno ou externo)."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT r.id, r.data_cobertura, r.data_parto, r.resultado, "
            "    t.brinco AS touro_brinco, r.touro_externo "
            "FROM reproducao r "
            "JOIN animais v ON r.vaca_id = v.id "
            "LEFT JOIN animais t ON r.touro_id = t.id "
            "WHERE r.vaca_id = %s AND v.user_id = %s "
            "ORDER BY r.data_cobertura DESC",
            (vaca_id, user_id)
        )
        return cursor.fetchall()
