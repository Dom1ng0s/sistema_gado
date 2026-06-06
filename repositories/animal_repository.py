from db_config import get_db_cursor
from datetime import datetime


def _build_animais_where(user_id, termo=None, status='todos', na_lixeira=False):
    conds = ["user_id = %s"]
    params = [user_id]
    if na_lixeira:
        conds.append("deleted_at IS NOT NULL")
    else:
        conds.append("deleted_at IS NULL")
    if termo:
        conds.append("brinco LIKE %s")
        params.append(f"{termo}%")
    if status == 'ativos':
        conds.append("data_venda IS NULL")
    elif status == 'vendidos':
        conds.append("data_venda IS NOT NULL")
    return "WHERE " + " AND ".join(conds), params


# ---- LISTAGENS E CONTAGENS ----

def count_animais(user_id, termo=None, status='todos'):
    where, params = _build_animais_where(user_id, termo, status)
    with get_db_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM animais " + where, tuple(params))
        return cursor.fetchone()[0]


def get_animais_paginados(user_id, limit, offset, termo=None, status='todos'):
    where, params = _build_animais_where(user_id, termo, status)
    sql = (
        "SELECT id, brinco, sexo, data_compra, preco_compra, data_venda, preco_venda "
        "FROM animais " + where +
        " ORDER BY LENGTH(brinco) ASC, brinco ASC LIMIT %s OFFSET %s"
    )
    with get_db_cursor() as cursor:
        cursor.execute(sql, tuple(params + [limit, offset]))
        return cursor.fetchall()


def count_animais_lixeira(user_id, termo=None):
    where, params = _build_animais_where(user_id, termo, na_lixeira=True)
    with get_db_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM animais " + where, tuple(params))
        return cursor.fetchone()[0]


def get_animais_lixeira_paginados(user_id, limit, offset, termo=None):
    where, params = _build_animais_where(user_id, termo, na_lixeira=True)
    sql = (
        "SELECT id, brinco, sexo, deleted_at FROM animais " + where +
        " ORDER BY deleted_at DESC LIMIT %s OFFSET %s"
    )
    with get_db_cursor() as cursor:
        cursor.execute(sql, tuple(params + [limit, offset]))
        return cursor.fetchall()


def get_animais_ativos(user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id, brinco FROM animais "
            "WHERE user_id = %s AND data_venda IS NULL AND deleted_at IS NULL "
            "ORDER BY brinco ASC",
            (user_id,)
        )
        return cursor.fetchall()


# ---- LEITURA DE ANIMAL ----

def get_animal_by_id(animal_id, user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM animais WHERE id = %s AND user_id = %s",
            (animal_id, user_id)
        )
        return cursor.fetchone()


def check_brinco_exists(brinco, user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id FROM animais WHERE brinco = %s AND user_id = %s",
            (brinco, user_id)
        )
        return cursor.fetchone() is not None


# ---- PESAGENS ----

def get_pesagens_by_animal(animal_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM pesagens WHERE animal_id = %s ORDER BY data_pesagem DESC",
            (animal_id,)
        )
        return cursor.fetchall()


def get_animal_id_by_pesagem(pesagem_id, user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT p.animal_id FROM pesagens p "
            "JOIN animais a ON p.animal_id = a.id "
            "WHERE p.id = %s AND a.user_id = %s",
            (pesagem_id, user_id)
        )
        res = cursor.fetchone()
        return res[0] if res else None


# ---- GMD ----

def get_gmd_by_animal(animal_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT peso_final, ganho_total, dias, gmd FROM v_gmd_analitico WHERE animal_id = %s",
            (animal_id,)
        )
        return cursor.fetchone()


def get_gmd_medio_rebanho(user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT AVG(v.gmd) FROM v_gmd_analitico v "
            "JOIN animais a ON v.animal_id = a.id "
            "WHERE v.user_id = %s AND a.data_venda IS NULL AND a.deleted_at IS NULL",
            (user_id,)
        )
        res = cursor.fetchone()
        return float(res[0]) if res and res[0] else 0.0


# ---- MEDICACOES ----

def get_medicacoes_by_animal(animal_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM medicacoes WHERE animal_id = %s",
            (animal_id,)
        )
        return cursor.fetchall()


# ---- GRAFICOS ----

def get_contagem_por_sexo(user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT sexo, COUNT(*) FROM animais "
            "WHERE user_id = %s AND data_venda IS NULL AND deleted_at IS NULL "
            "GROUP BY sexo",
            (user_id,)
        )
        return cursor.fetchall()


def get_pesos_atuais_rebanho(user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT p.peso FROM pesagens p "
            "INNER JOIN (SELECT animal_id, MAX(id) AS m FROM pesagens GROUP BY animal_id) u ON p.id = u.m "
            "INNER JOIN animais a ON p.animal_id = a.id "
            "WHERE a.user_id = %s AND a.data_venda IS NULL AND a.deleted_at IS NULL",
            (user_id,)
        )
        return cursor.fetchall()


# ---- ESCRITAS ATÔMICAS ----

def cadastrar_animal(brinco, sexo, data_compra, preco_compra, peso_entrada, user_id):
    """Insere animal e pesagem inicial na mesma transação. Retorna animal_id."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id) VALUES (%s, %s, %s, %s, %s)",
            (brinco, sexo, data_compra, preco_compra, user_id)
        )
        animal_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)",
            (animal_id, data_compra, peso_entrada)
        )
        return animal_id


def registrar_venda(animal_id, user_id, data_venda, preco_venda, peso_venda):
    """Atualiza venda e registra pesagem final na mesma transação. Retorna True se o animal pertence ao usuário."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id FROM animais WHERE id = %s AND user_id = %s",
            (animal_id, user_id)
        )
        if not cursor.fetchone():
            return False
        cursor.execute(
            "UPDATE animais SET data_venda = %s, preco_venda = %s WHERE id = %s",
            (data_venda, preco_venda, animal_id)
        )
        cursor.execute(
            "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)",
            (animal_id, data_venda, peso_venda)
        )
        return True


def registrar_pesagem(animal_id, user_id, data_pesagem, peso):
    """Valida propriedade e insere pesagem na mesma transação. Retorna True se bem-sucedido."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id FROM animais WHERE id = %s AND user_id = %s",
            (animal_id, user_id)
        )
        if not cursor.fetchone():
            return False
        cursor.execute(
            "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)",
            (animal_id, data_pesagem, peso)
        )
        return True


def registrar_medicacao(animal_id, user_id, data_aplicacao, nome, custo, obs):
    """Valida propriedade e insere medicação na mesma transação. Retorna True se bem-sucedido."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id FROM animais WHERE id = %s AND user_id = %s",
            (animal_id, user_id)
        )
        if not cursor.fetchone():
            return False
        cursor.execute(
            "INSERT INTO medicacoes (animal_id, data_aplicacao, nome_medicamento, custo, observacoes) "
            "VALUES (%s, %s, %s, %s, %s)",
            (animal_id, data_aplicacao, nome, custo, obs)
        )
        return True


def insert_medicacao_lote(animal_ids, data_aplicacao, nome, custo, obs):
    """Insere medicação em múltiplos animais na mesma transação."""
    with get_db_cursor() as cursor:
        for animal_id in animal_ids:
            cursor.execute(
                "INSERT INTO medicacoes (animal_id, data_aplicacao, nome_medicamento, custo, observacoes) "
                "VALUES (%s, %s, %s, %s, %s)",
                (animal_id, data_aplicacao, nome, custo, obs)
            )


def soft_delete_animal(animal_id, user_id):
    """Soft delete com verificação de propriedade. Retorna True se o animal pertence ao usuário."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id FROM animais WHERE id = %s AND user_id = %s",
            (animal_id, user_id)
        )
        if not cursor.fetchone():
            return False
        cursor.execute(
            "UPDATE animais SET deleted_at = %s WHERE id = %s",
            (datetime.now(), animal_id)
        )
        return True


def soft_delete_pesagem(pesagem_id, user_id):
    """Soft delete da pesagem verificando que pertence ao usuário. Retorna animal_id ou None."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT p.animal_id FROM pesagens p "
            "JOIN animais a ON p.animal_id = a.id "
            "WHERE p.id = %s AND a.user_id = %s",
            (pesagem_id, user_id)
        )
        res = cursor.fetchone()
        if not res:
            return None
        animal_id = res[0]
        cursor.execute(
            "UPDATE pesagens SET deleted_at = %s WHERE id = %s",
            (datetime.now(), pesagem_id)
        )
        return animal_id


def restore_animal(animal_id, user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "UPDATE animais SET deleted_at = NULL WHERE id = %s AND user_id = %s",
            (animal_id, user_id)
        )


def cadastrar_lote(user_id, codigo_lote, descricao, data_compra, animais_data):
    """
    Insere lote e todos os seus animais/pesagens em uma única transação.
    animais_data: lista de (brinco, sexo, peso_kg, custo_animal)
    Retorna lote_id.
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO lotes (user_id, codigo_lote, descricao, data_aquisicao) VALUES (%s, %s, %s, %s)",
            (user_id, codigo_lote, descricao, data_compra)
        )
        lote_id = cursor.lastrowid
        for brinco, sexo, peso, custo_animal in animais_data:
            cursor.execute(
                "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id, lote_id) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (brinco, sexo, data_compra, custo_animal, user_id, lote_id)
            )
            animal_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)",
                (animal_id, data_compra, peso)
            )
        return lote_id
