from db_config import get_db_cursor
from datetime import datetime


# ATENÇÃO: `conds` deve conter apenas literais hardcoded (ex.: "deleted_at IS NULL").
# Dados externos (usuário, banco, request) nunca devem ser interpolados em `conds` —
# sempre vão para `params` e chegam ao banco via placeholder %s.
# Adicionar um valor externo diretamente em `conds` introduz risco de SQL injection.
def _build_animais_where(user_id, termo=None, status='todos', na_lixeira=False, raca=None):
    conds = ["user_id = %s"]
    params = [user_id]
    if na_lixeira:
        conds.append("deleted_at IS NOT NULL")
    else:
        conds.append("deleted_at IS NULL")
    if termo:
        conds.append("brinco LIKE %s")
        params.append(termo + "%")
    if status == 'ativos':
        conds.append("data_venda IS NULL")
    elif status == 'vendidos':
        conds.append("data_venda IS NOT NULL")
    if raca:
        conds.append("raca = %s")
        params.append(raca)
    return "WHERE " + " AND ".join(conds), params


# ---- LISTAGENS E CONTAGENS ----

def count_animais(user_id, termo=None, status='todos', raca=None):
    where, params = _build_animais_where(user_id, termo, status, raca=raca)
    with get_db_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM animais " + where, tuple(params))
        return cursor.fetchone()[0]


def get_animais_paginados(user_id, limit, offset, termo=None, status='todos', raca=None):
    conds = ["a.user_id = %s", "a.deleted_at IS NULL"]
    params = [user_id]
    if termo:
        conds.append("a.brinco LIKE %s")
        params.append(termo + "%")
    if status == 'ativos':
        conds.append("a.data_venda IS NULL")
    elif status == 'vendidos':
        conds.append("a.data_venda IS NOT NULL")
    if raca:
        conds.append("a.raca = %s")
        params.append(raca)
    where = "WHERE " + " AND ".join(conds)
    sql = (
        "SELECT a.id, a.brinco, a.sexo, a.raca, a.data_compra, a.preco_compra, "
        "       a.data_venda, a.preco_venda "
        "FROM animais a "
        + where +
        " ORDER BY LENGTH(a.brinco) ASC, a.brinco ASC LIMIT %s OFFSET %s"
    )
    with get_db_cursor() as cursor:
        cursor.execute(sql, tuple(params + [limit, offset]))
        return cursor.fetchall()


def get_gmd_lote(animal_ids: list, user_id: int) -> dict:
    """Retorna {str(animal_id): [peso_final, gmd]} para os IDs informados.

    Consulta pesagens diretamente (não a view CTE) para que o índice
    em pesagens(animal_id) seja aproveitado. user_id validado via JOIN.
    """
    if not animal_ids:
        return {}
    placeholders = '(' + ','.join(['%s'] * len(animal_ids)) + ')'
    sql = (
        "WITH po AS ("
        "  SELECT p.animal_id, p.data_pesagem, p.peso,"
        "    ROW_NUMBER() OVER (PARTITION BY p.animal_id ORDER BY p.data_pesagem ASC)  AS rn_asc,"
        "    ROW_NUMBER() OVER (PARTITION BY p.animal_id ORDER BY p.data_pesagem DESC) AS rn_desc"
        "  FROM pesagens p"
        "  JOIN animais a ON a.id = p.animal_id AND a.user_id = %s AND a.deleted_at IS NULL"
        "  WHERE p.animal_id IN " + placeholders +
        "),"
        " pu AS ("
        "  SELECT animal_id,"
        "    MAX(CASE WHEN rn_asc  = 1 THEN data_pesagem END) AS data_ini,"
        "    MAX(CASE WHEN rn_asc  = 1 THEN peso END)         AS peso_ini,"
        "    MAX(CASE WHEN rn_desc = 1 THEN data_pesagem END) AS data_fim,"
        "    MAX(CASE WHEN rn_desc = 1 THEN peso END)         AS peso_fim"
        "  FROM po GROUP BY animal_id"
        " )"
        " SELECT animal_id, peso_fim,"
        "  CASE WHEN DATEDIFF(data_fim, data_ini) > 0"
        "    THEN ROUND((peso_fim - peso_ini) / DATEDIFF(data_fim, data_ini), 3)"
        "    ELSE NULL END AS gmd"
        " FROM pu"
    )
    params = [user_id] + list(animal_ids)
    with get_db_cursor() as cursor:
        cursor.execute(sql, tuple(params))
        return {str(row[0]): [row[1], row[2]] for row in cursor.fetchall()}


def get_racas_distintas(user_id):
    """Raças únicas cadastradas pelo usuário (para filtro no painel)."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT DISTINCT raca FROM animais "
            "WHERE user_id = %s AND raca IS NOT NULL AND raca != '' "
            "AND deleted_at IS NULL ORDER BY raca",
            (user_id,)
        )
        return [row[0] for row in cursor.fetchall()]


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


def get_lotes(user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id, codigo_lote FROM lotes "
            "WHERE user_id = %s AND deleted_at IS NULL "
            "ORDER BY data_aquisicao DESC",
            (user_id,)
        )
        return cursor.fetchall()


def get_animais_ativos_por_lote(user_id, lote_id=None):
    with get_db_cursor() as cursor:
        if lote_id:
            cursor.execute(
                "SELECT id, brinco FROM animais "
                "WHERE user_id = %s AND data_venda IS NULL AND deleted_at IS NULL "
                "AND lote_id = %s ORDER BY brinco ASC",
                (user_id, lote_id)
            )
        else:
            cursor.execute(
                "SELECT id, brinco FROM animais "
                "WHERE user_id = %s AND data_venda IS NULL AND deleted_at IS NULL "
                "ORDER BY brinco ASC",
                (user_id,)
            )
        return cursor.fetchall()


def registrar_pesagens_lote(pairs, user_id, data_pesagem):
    """Insere múltiplas pesagens em uma única transação.

    pairs: lista de (animal_id, peso).
    Valida que todos os animal_ids pertencem ao user_id antes de inserir.
    Retorna (inseridos, ids_invalidos).
    """
    if not pairs:
        return 0, []

    animal_ids = [p[0] for p in pairs]
    placeholders = ','.join(['%s'] * len(animal_ids))

    with get_db_cursor() as cursor:
        cursor.execute(
            f"SELECT id FROM animais WHERE id IN ({placeholders}) AND user_id = %s",
            animal_ids + [user_id]
        )
        validos = {row[0] for row in cursor.fetchall()}
        invalidos = [aid for aid in animal_ids if aid not in validos]

        inseridos = 0
        for animal_id, peso in pairs:
            if animal_id in validos:
                cursor.execute(
                    "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)",
                    (animal_id, data_pesagem, peso)
                )
                inseridos += 1

    return inseridos, invalidos


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


def get_animais_com_gmd(user_id):
    """Animais ativos com GMD (LEFT JOIN — inclui animais sem pesagem)."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT a.id, a.brinco, a.sexo, a.raca, a.data_compra, "
            "       v.gmd, v.dias, v.peso_final "
            "FROM animais a "
            "LEFT JOIN v_gmd_analitico v ON a.id = v.animal_id "
            "WHERE a.user_id = %s AND a.data_venda IS NULL AND a.deleted_at IS NULL "
            "ORDER BY LENGTH(a.brinco), a.brinco",
            (user_id,)
        )
        return cursor.fetchall()


def get_animais_abaixo_gmd_medio(user_id):
    """Animais ativos com GMD abaixo de (média - 2σ): outliers estatísticos do rebanho."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT sub.animal_id, a.brinco, sub.gmd, sub.gmd_media, "
            "       sub.gmd_std, (sub.gmd_media - 2 * sub.gmd_std) AS limite_inferior "
            "FROM ( "
            "    SELECT v.animal_id, v.gmd, "
            "           AVG(v.gmd) OVER () AS gmd_media, "
            "           STDDEV_POP(v.gmd) OVER () AS gmd_std "
            "    FROM v_gmd_analitico v "
            "    JOIN animais a ON v.animal_id = a.id "
            "    WHERE v.user_id = %s "
            "      AND a.data_venda IS NULL AND a.deleted_at IS NULL "
            ") sub "
            "JOIN animais a ON sub.animal_id = a.id "
            "WHERE sub.gmd < (sub.gmd_media - 2 * sub.gmd_std) "
            "ORDER BY sub.gmd ASC",
            (user_id,)
        )
        return cursor.fetchall()


# ---- HEREDITARIEDADE ----

def get_animais_ativos_por_sexo(user_id, sexo):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id, brinco FROM animais "
            "WHERE user_id = %s AND sexo = %s AND data_venda IS NULL AND deleted_at IS NULL "
            "ORDER BY brinco ASC",
            (user_id, sexo)
        )
        return cursor.fetchall()


def get_progenie_by_touro(animal_id, user_id):
    """Filhos onde animal é pai (pai_id) OU mãe (mae_id)."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT f.id, f.brinco, f.sexo, f.data_compra, g.gmd, "
            "    CASE WHEN f.pai_id = %s THEN 'pai' ELSE 'mae' END AS papel "
            "FROM animais f "
            "LEFT JOIN v_gmd_analitico g ON g.animal_id = f.id "
            "WHERE (f.pai_id = %s OR f.mae_id = %s) "
            "  AND f.user_id = %s AND f.deleted_at IS NULL "
            "ORDER BY f.brinco",
            (animal_id, animal_id, animal_id, user_id)
        )
        return cursor.fetchall()


def get_historico_reproducao(vaca_id, user_id):
    """Estatísticas agregadas da vw_historico_vaca para a vaca."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT vaca_id, total_coberturas, partos_vivos, taxa_sucesso, "
            "    primeira_cobertura, ultima_cobertura "
            "FROM vw_historico_vaca "
            "WHERE vaca_id = %s AND user_id = %s",
            (vaca_id, user_id)
        )
        return cursor.fetchone()


def get_ranking_touros(user_id):
    """Ranking de touros por GMD médio dos filhos (vw_gmd_por_touro)."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT touro_id, touro_brinco, touro_raca, qtd_filhos, gmd_medio_filhos "
            "FROM vw_gmd_por_touro WHERE user_id = %s "
            "ORDER BY gmd_medio_filhos DESC",
            (user_id,)
        )
        return cursor.fetchall()


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

def cadastrar_animal(brinco, sexo, data_compra, preco_compra, peso_entrada, user_id,
                     data_nascimento=None, mae_id=None, pai_id=None, raca=None):
    """Insere animal e pesagem inicial (quando disponível) na mesma transação. Retorna animal_id.

    Animais nascidos na fazenda passam data_compra=None e data_nascimento preenchida.
    Pesagem inicial só é inserida se peso_entrada for fornecido (> 0).
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO animais "
            "(brinco, sexo, raca, data_compra, data_nascimento, preco_compra, user_id, mae_id, pai_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (brinco, sexo, raca or None, data_compra or None, data_nascimento or None,
             preco_compra or None, user_id, mae_id or None, pai_id or None)
        )
        animal_id = cursor.lastrowid
        data_ref = data_compra or data_nascimento
        if peso_entrada and data_ref:
            cursor.execute(
                "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)",
                (animal_id, data_ref, peso_entrada)
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


def cadastrar_lote(user_id, codigo_lote, descricao, data_compra, animais_data, raca=None):
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
                "INSERT INTO animais (brinco, sexo, raca, data_compra, preco_compra, user_id, lote_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (brinco, sexo, raca or None, data_compra, custo_animal, user_id, lote_id)
            )
            animal_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)",
                (animal_id, data_compra, peso)
            )
        return lote_id
