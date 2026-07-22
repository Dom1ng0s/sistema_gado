from db_config import get_db_cursor


# ---- PASTOS ----

def get_pastos(user_id, termo=None):
    """Lista pastos do usuário com contagem de módulos e alertas de lotação.

    Um único LEFT JOIN agregado em vez de 3 subqueries correlacionadas por
    linha — vw_ocupacao_atual já é uma view com GROUP BY por módulo, então
    reprocessá-la 2x por pasto era redundante.
    """
    where = "WHERE p.user_id = %s"
    params = [user_id]
    if termo:
        where += " AND p.nome LIKE %s"
        params.append(termo + "%")
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT p.id, p.nome, p.area_hectares, p.forrageira, p.capacidade_ua, "
            "    COUNT(DISTINCT m.id) AS qtd_modulos, "
            "    COUNT(DISTINCT CASE WHEN va.pct_lotacao > 100 THEN va.modulo_id END) AS superlotados, "
            "    COUNT(DISTINCT CASE WHEN va.pct_lotacao BETWEEN 80 AND 100 THEN va.modulo_id END) AS em_alerta "
            "FROM pastos p "
            "LEFT JOIN modulos m ON m.pasto_id = p.id "
            "LEFT JOIN vw_ocupacao_atual va ON va.modulo_id = m.id "
            + where +
            " GROUP BY p.id, p.nome, p.area_hectares, p.forrageira, p.capacidade_ua "
            "ORDER BY p.nome",
            tuple(params)
        )
        return cursor.fetchall()


def insert_pasto(user_id, nome, area_hectares, forrageira, capacidade_ua):
    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO pastos (user_id, nome, area_hectares, forrageira, capacidade_ua) "
            "VALUES (%s, %s, %s, %s, %s)",
            (user_id, nome, area_hectares, forrageira, capacidade_ua)
        )
        return cursor.lastrowid


def get_pasto_by_id(pasto_id, user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id, nome, area_hectares, forrageira, capacidade_ua "
            "FROM pastos WHERE id = %s AND user_id = %s",
            (pasto_id, user_id)
        )
        return cursor.fetchone()


# ---- MÓDULOS ----

def get_modulos_by_pasto(pasto_id, user_id):
    """Retorna módulos com status de ocupação (vw_ocupacao_atual) e descanso (vw_dias_descanso)."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT m.id, m.nome, m.area_hectares, m.capacidade_ua, "
            "    va.ua_atual, va.pct_lotacao, va.ocupacao_id, va.data_entrada, "
            "    vd.dias_descanso, vd.ultima_saida "
            "FROM modulos m "
            "LEFT JOIN vw_ocupacao_atual va ON va.modulo_id = m.id "
            "LEFT JOIN vw_dias_descanso vd ON vd.modulo_id = m.id "
            "WHERE m.pasto_id = %s AND m.user_id = %s "
            "ORDER BY m.nome",
            (pasto_id, user_id)
        )
        return cursor.fetchall()


def insert_modulo(pasto_id, user_id, nome, area_hectares, capacidade_ua):
    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO modulos (pasto_id, user_id, nome, area_hectares, capacidade_ua) "
            "VALUES (%s, %s, %s, %s, %s)",
            (pasto_id, user_id, nome, area_hectares, capacidade_ua)
        )
        return cursor.lastrowid


def get_modulo_by_id(modulo_id, user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id, nome, area_hectares, capacidade_ua, pasto_id "
            "FROM modulos WHERE id = %s AND user_id = %s",
            (modulo_id, user_id)
        )
        return cursor.fetchone()


# ---- OCUPAÇÕES ----

def get_ocupacao_ativa(modulo_id, user_id):
    """Retorna (ocupacao_id, data_entrada) da ocupação ativa ou None."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT o.id, o.data_entrada FROM ocupacoes o "
            "JOIN modulos m ON o.modulo_id = m.id "
            "WHERE o.modulo_id = %s AND m.user_id = %s AND o.data_saida IS NULL",
            (modulo_id, user_id)
        )
        return cursor.fetchone()


def iniciar_ocupacao(modulo_id, user_id, data_entrada, animal_ids):
    """Insere ocupacao e ocupacao_animais em uma única transação.

    Valida que todos os animal_ids pertencem ao user_id antes de inserir —
    mesmo padrão de animal_repository.registrar_pesagens_lote.
    Retorna ocupacao_id.

    IDs de outro tenant são descartados em silêncio: o form só lista os animais
    do próprio usuário, então isso só ocorre em POST forjado.
    """
    ids = []
    for aid in animal_ids:
        try:
            ids.append(int(aid))
        except (TypeError, ValueError):
            continue

    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO ocupacoes (modulo_id, user_id, data_entrada) VALUES (%s, %s, %s)",
            (modulo_id, user_id, data_entrada)
        )
        ocupacao_id = cursor.lastrowid

        validos = set()
        if ids:
            placeholders = ','.join(['%s'] * len(ids))
            cursor.execute(
                f"SELECT id FROM animais WHERE id IN ({placeholders}) "
                f"AND user_id = %s AND deleted_at IS NULL",
                ids + [user_id]
            )
            validos = {row[0] for row in cursor.fetchall()}

        if validos:
            cursor.executemany(
                "INSERT INTO ocupacao_animais (ocupacao_id, animal_id) VALUES (%s, %s)",
                [(ocupacao_id, aid) for aid in validos]
            )

        return ocupacao_id


def encerrar_ocupacao(ocupacao_id, user_id, data_saida):
    """Verifica ownership via modulo e registra data_saida. Retorna True/False."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT o.id FROM ocupacoes o "
            "JOIN modulos m ON o.modulo_id = m.id "
            "WHERE o.id = %s AND m.user_id = %s AND o.data_saida IS NULL",
            (ocupacao_id, user_id)
        )
        if not cursor.fetchone():
            return False
        cursor.execute(
            "UPDATE ocupacoes SET data_saida = %s WHERE id = %s",
            (data_saida, ocupacao_id)
        )
        return True


def get_pasto_id_by_ocupacao(ocupacao_id, user_id):
    """Retorna o pasto_id do módulo dono da ocupação, com checagem de ownership."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT m.pasto_id FROM ocupacoes o "
            "JOIN modulos m ON o.modulo_id = m.id "
            "WHERE o.id = %s AND m.user_id = %s",
            (ocupacao_id, user_id)
        )
        row = cursor.fetchone()
        return row[0] if row else None


def get_animais_ocupacoes_ativas(pasto_id, user_id):
    """Retorna (ocupacao_id, animal_id, brinco) para ocupações ativas do pasto."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT o.id, a.id, a.brinco "
            "FROM ocupacoes o "
            "JOIN ocupacao_animais oa ON oa.ocupacao_id = o.id "
            "JOIN animais a ON a.id = oa.animal_id "
            "JOIN modulos m ON m.id = o.modulo_id "
            "WHERE m.pasto_id = %s AND m.user_id = %s AND o.data_saida IS NULL "
            "ORDER BY a.brinco",
            (pasto_id, user_id)
        )
        return cursor.fetchall()


# ---- VIEWS ----

def get_ocupacao_atual(user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT modulo_id, pasto_id, modulo_nome, capacidade_ua, "
            "    ua_atual, pct_lotacao, ocupacao_id, data_entrada "
            "FROM vw_ocupacao_atual WHERE user_id = %s",
            (user_id,)
        )
        return cursor.fetchall()


def get_dias_descanso(user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT modulo_id, pasto_id, modulo_nome, ultima_saida, dias_descanso "
            "FROM vw_dias_descanso WHERE user_id = %s",
            (user_id,)
        )
        return cursor.fetchall()


def get_gmd_por_modulo(user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT modulo_id, modulo_nome, pasto_id, qtd_animais, gmd_medio "
            "FROM vw_gmd_por_modulo WHERE user_id = %s "
            "ORDER BY gmd_medio DESC",
            (user_id,)
        )
        return cursor.fetchall()


def get_top_gmd_por_modulo(user_id, limit=5):
    """Top módulos por GMD médio, incluindo nome do pasto."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT g.modulo_nome, p.nome AS pasto_nome, g.gmd_medio, g.qtd_animais "
            "FROM vw_gmd_por_modulo g "
            "JOIN pastos p ON p.id = g.pasto_id "
            "WHERE g.user_id = %s AND g.gmd_medio IS NOT NULL "
            "ORDER BY g.gmd_medio DESC LIMIT %s",
            (user_id, limit)
        )
        return cursor.fetchall()
