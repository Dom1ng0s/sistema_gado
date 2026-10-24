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
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (user_id, nome, descricao or None, intervalo_dias, proxima_aplicacao)
        )
        return cursor.fetchone()[0]


def get_vencendo_em_dias(user_id, dias=7):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id, nome, proxima_aplicacao, intervalo_dias "
            "FROM protocolos_sanitarios "
            "WHERE user_id = %s AND ativo = 1 "
            "AND proxima_aplicacao <= CURRENT_DATE + %s "
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
            "SET proxima_aplicacao = proxima_aplicacao + intervalo_dias "
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


# ---- CARÊNCIA SANITÁRIA ----

def get_carencias_ativas(user_id, animal_ids=None):
    """Aplicações ainda em carência, da view `vw_animais_em_carencia`.

    Retorna tuplas (animal_id, brinco, medicacao_id, nome_medicamento,
    data_aplicacao, dias_carencia, data_liberacao, dias_restantes), do
    vencimento mais distante para o mais próximo — o primeiro é o que manda na
    liberação do animal.

    `animal_ids=None` devolve tudo da fazenda (card do /inicio); com ids, filtra
    (guarda da venda). Lista vazia devolve [] sem ir ao banco.
    """
    if animal_ids is not None and not animal_ids:
        return []
    sql = (
        "SELECT animal_id, brinco, medicacao_id, nome_medicamento, data_aplicacao, "
        "       dias_carencia, data_liberacao, dias_restantes "
        "FROM vw_animais_em_carencia WHERE user_id = %s"
    )
    params = [user_id]
    if animal_ids is not None:
        sql += " AND animal_id = ANY(%s)"
        params.append([int(a) for a in animal_ids])
    sql += " ORDER BY data_liberacao DESC, brinco ASC"
    with get_db_cursor() as cursor:
        cursor.execute(sql, tuple(params))
        return cursor.fetchall()


def registrar_override_carencia(carencias, autorizado_por):
    """Grava a autorização de venda dentro da carência.

    `carencias` são as tuplas devolvidas por `get_carencias_ativas`. Override sem
    registro não serve de nada: se a carcaça for rejeitada, esta tabela é a única
    resposta para "quem liberou".
    """
    if not carencias:
        return 0
    linhas = [(c[0], c[2], autorizado_por, c[6]) for c in carencias]
    with get_db_cursor() as cursor:
        cursor.executemany(
            "INSERT INTO vendas_com_carencia "
            "(animal_id, medicacao_id, autorizado_por, data_liberacao) "
            "VALUES (%s, %s, %s, %s)",
            linhas
        )
    return len(linhas)
