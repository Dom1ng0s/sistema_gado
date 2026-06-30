from db_config import get_db_cursor


def get_configuracao(user_id):
    """Retorna (nome_fazenda, cidade_estado, area_total, gmd_meta) ou None se não configurado."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT nome_fazenda, cidade_estado, area_total, gmd_meta "
            "FROM configuracoes WHERE user_id = %s",
            (user_id,)
        )
        return cursor.fetchone()


def upsert_configuracao(user_id, nome_fazenda, cidade_estado, area_total, gmd_meta=0.800):
    """Cria ou atualiza as configurações do usuário (INSERT … ON DUPLICATE KEY UPDATE)."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO configuracoes (user_id, nome_fazenda, cidade_estado, area_total, gmd_meta) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "nome_fazenda = VALUES(nome_fazenda), "
            "cidade_estado = VALUES(cidade_estado), "
            "area_total = VALUES(area_total), "
            "gmd_meta = VALUES(gmd_meta)",
            (user_id, nome_fazenda, cidade_estado, area_total, gmd_meta)
        )
