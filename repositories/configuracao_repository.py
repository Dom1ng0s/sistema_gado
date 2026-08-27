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
    """Cria ou atualiza as configurações do usuário (INSERT … ON CONFLICT DO UPDATE)."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO configuracoes (user_id, nome_fazenda, cidade_estado, area_total, gmd_meta) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (user_id) DO UPDATE SET "
            "nome_fazenda = EXCLUDED.nome_fazenda, "
            "cidade_estado = EXCLUDED.cidade_estado, "
            "area_total = EXCLUDED.area_total, "
            "gmd_meta = EXCLUDED.gmd_meta",
            (user_id, nome_fazenda, cidade_estado, area_total, gmd_meta)
        )
