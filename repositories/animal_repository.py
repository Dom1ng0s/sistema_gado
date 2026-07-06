from db_config import get_db_cursor
from datetime import datetime


# ATENÇÃO: `conds` deve conter apenas literais hardcoded (ex.: "deleted_at IS NULL").
# Dados externos (usuário, banco, request) nunca devem ser interpolados em `conds` —
# sempre vão para `params` e chegam ao banco via placeholder %s.
# Adicionar um valor externo diretamente em `conds` introduz risco de SQL injection.
def _build_animais_where(user_id, termo=None, status='todos', na_lixeira=False, raca=None, origem=None, sexo=None, alias=''):
    conds = [f"{alias}user_id = %s"]
    params = [user_id]
    if na_lixeira:
        conds.append(f"{alias}deleted_at IS NOT NULL")
    else:
        conds.append(f"{alias}deleted_at IS NULL")
    if termo:
        conds.append(f"{alias}brinco LIKE %s")
        params.append(termo + "%")
    if status == 'ativos':
        conds.append(f"{alias}data_venda IS NULL")
    elif status == 'vendidos':
        conds.append(f"{alias}data_venda IS NOT NULL")
    if raca:
        conds.append(f"{alias}raca = %s")
        params.append(raca)
    if sexo in ('M', 'F'):
        conds.append(f"{alias}sexo = %s")
        params.append(sexo)
    if origem == 'fazenda':
        conds.append(f"{alias}data_compra IS NULL AND {alias}data_nascimento IS NOT NULL")
    return "WHERE " + " AND ".join(conds), params


def _origem_cond(origem, alias='a.'):
    """Mesma condição de 'nascido na fazenda' usada em _build_animais_where, para
    as CTEs de GMD que montam o JOIN com animais manualmente."""
    if origem == 'fazenda':
        return f" AND {alias}data_compra IS NULL AND {alias}data_nascimento IS NOT NULL"
    return ""


# ---- LISTAGENS E CONTAGENS ----

def count_animais(user_id, termo=None, status='todos', raca=None, origem=None, sexo=None):
    where, params = _build_animais_where(user_id, termo, status, raca=raca, origem=origem, sexo=sexo)
    with get_db_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM animais " + where, tuple(params))
        return cursor.fetchone()[0]


def get_animais_paginados(user_id, limit, offset, termo=None, status='todos', raca=None, origem=None, sexo=None):
    where, params = _build_animais_where(user_id, termo, status, raca=raca, origem=origem, sexo=sexo, alias='a.')
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
        "  WHERE p.animal_id IN " + placeholders + " AND p.deleted_at IS NULL"
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


def get_animais_ativos_com_ultimo_peso(user_id):
    """Animais ativos com o peso da pesagem mais recente (None se nunca pesado)."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "WITH ultimo AS ("
            "  SELECT p.animal_id, p.peso,"
            "    ROW_NUMBER() OVER (PARTITION BY p.animal_id ORDER BY p.data_pesagem DESC, p.id DESC) AS rn"
            "  FROM pesagens p WHERE p.deleted_at IS NULL"
            ")"
            " SELECT a.id, a.brinco, a.raca, u.peso AS ultimo_peso"
            " FROM animais a"
            " LEFT JOIN ultimo u ON u.animal_id = a.id AND u.rn = 1"
            " WHERE a.user_id = %s AND a.data_venda IS NULL AND a.deleted_at IS NULL"
            " ORDER BY LENGTH(a.brinco), a.brinco",
            (user_id,)
        )
        return cursor.fetchall()


def get_lotes(user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id, codigo_lote FROM lotes "
            "WHERE user_id = %s "
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
            f"SELECT id FROM animais WHERE id IN ({placeholders}) AND user_id = %s AND deleted_at IS NULL",
            animal_ids + [user_id]
        )
        validos = {row[0] for row in cursor.fetchall()}
        invalidos = [aid for aid in animal_ids if aid not in validos]

        pares_validos = [(aid, data_pesagem, peso) for aid, peso in pairs if aid in validos]
        if pares_validos:
            cursor.executemany(
                "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)",
                pares_validos
            )

    return len(pares_validos), invalidos


# ---- LEITURA DE ANIMAL ----

def get_animal_by_id(animal_id, user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id, brinco, sexo, raca, data_compra, preco_compra, "
            "data_venda, preco_venda, user_id, lote_id, deleted_at, "
            "pai_id, mae_id, data_nascimento "
            "FROM animais WHERE id = %s AND user_id = %s",
            (animal_id, user_id)
        )
        return cursor.fetchone()


def check_brinco_exists(brinco, user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id FROM animais WHERE brinco = %s AND user_id = %s AND deleted_at IS NULL",
            (brinco, user_id)
        )
        return cursor.fetchone() is not None


# ---- PESAGENS ----

def get_pesagens_by_animal(animal_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id, animal_id, data_pesagem, peso, deleted_at "
            "FROM pesagens WHERE animal_id = %s AND deleted_at IS NULL "
            "ORDER BY data_pesagem DESC",
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
    """GMD de um animal calculado diretamente sobre pesagens — sem view CTE global."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "WITH po AS ("
            "  SELECT data_pesagem, peso,"
            "    ROW_NUMBER() OVER (ORDER BY data_pesagem ASC)  AS rn_asc,"
            "    ROW_NUMBER() OVER (ORDER BY data_pesagem DESC) AS rn_desc"
            "  FROM pesagens WHERE animal_id = %s AND deleted_at IS NULL"
            "),"
            " pu AS ("
            "  SELECT"
            "    MAX(CASE WHEN rn_asc  = 1 THEN data_pesagem END) AS data_ini,"
            "    MAX(CASE WHEN rn_asc  = 1 THEN peso END)         AS peso_ini,"
            "    MAX(CASE WHEN rn_desc = 1 THEN data_pesagem END) AS data_fim,"
            "    MAX(CASE WHEN rn_desc = 1 THEN peso END)         AS peso_fim"
            "  FROM po"
            " )"
            " SELECT peso_fim AS peso_final,"
            "  (peso_fim - peso_ini) AS ganho_total,"
            "  DATEDIFF(data_fim, data_ini) AS dias,"
            "  CASE WHEN DATEDIFF(data_fim, data_ini) > 0"
            "    THEN ROUND((peso_fim - peso_ini) / DATEDIFF(data_fim, data_ini), 3)"
            "    ELSE 0 END AS gmd"
            " FROM pu WHERE data_ini <> data_fim",
            (animal_id,)
        )
        return cursor.fetchone()


def get_gmd_medio_rebanho(user_id, sexo=None, origem=None):
    """AVG do GMD calculado diretamente sobre pesagens — sem materializar v_gmd_analitico.

    Filtra user_id no JOIN com animais antes das window functions, evitando
    que o MySQL varra pesagens de todos os usuários antes de restringir ao tenant.
    `sexo` ('M'/'F') restringe o rebanho considerado no cálculo — usado para
    segregar matrizes (GMD baixo por natureza) do restante do plantel.
    `origem='fazenda'` restringe aos animais nascidos na própria fazenda,
    mesmo filtro de origem aplicado à listagem via _build_animais_where.
    """
    sexo_cond = " AND a.sexo = %s" if sexo in ('M', 'F') else ""
    origem_cond = _origem_cond(origem)
    params = [user_id] + ([sexo] if sexo in ('M', 'F') else [])
    with get_db_cursor() as cursor:
        cursor.execute(
            "WITH po AS ("
            "  SELECT p.animal_id, p.data_pesagem, p.peso,"
            "    ROW_NUMBER() OVER (PARTITION BY p.animal_id ORDER BY p.data_pesagem ASC)  AS rn_asc,"
            "    ROW_NUMBER() OVER (PARTITION BY p.animal_id ORDER BY p.data_pesagem DESC) AS rn_desc"
            "  FROM pesagens p"
            "  JOIN animais a ON a.id = p.animal_id"
            "    AND a.user_id = %s AND a.deleted_at IS NULL AND a.data_venda IS NULL"
            "    AND p.deleted_at IS NULL"
            f"    {sexo_cond}{origem_cond}"
            "),"
            " pu AS ("
            "  SELECT animal_id,"
            "    MAX(CASE WHEN rn_asc  = 1 THEN data_pesagem END) AS data_ini,"
            "    MAX(CASE WHEN rn_asc  = 1 THEN peso END)         AS peso_ini,"
            "    MAX(CASE WHEN rn_desc = 1 THEN data_pesagem END) AS data_fim,"
            "    MAX(CASE WHEN rn_desc = 1 THEN peso END)         AS peso_fim"
            "  FROM po GROUP BY animal_id"
            " )"
            " SELECT AVG(CASE WHEN DATEDIFF(data_fim, data_ini) > 0"
            "   THEN (peso_fim - peso_ini) / DATEDIFF(data_fim, data_ini) END)"
            " FROM pu WHERE data_ini <> data_fim",
            tuple(params)
        )
        res = cursor.fetchone()
        return float(res[0]) if res and res[0] else 0.0


def get_animais_com_gmd(user_id):
    """Animais ativos com GMD — CTE inline, sem v_gmd_analitico."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "WITH po AS ("
            "  SELECT p.animal_id, p.data_pesagem, p.peso,"
            "    ROW_NUMBER() OVER (PARTITION BY p.animal_id ORDER BY p.data_pesagem ASC)  AS rn_asc,"
            "    ROW_NUMBER() OVER (PARTITION BY p.animal_id ORDER BY p.data_pesagem DESC) AS rn_desc"
            "  FROM pesagens p"
            "  JOIN animais a ON a.id = p.animal_id"
            "    AND a.user_id = %s AND a.data_venda IS NULL AND a.deleted_at IS NULL"
            "    AND p.deleted_at IS NULL"
            "),"
            " pu AS ("
            "  SELECT animal_id,"
            "    MAX(CASE WHEN rn_asc  = 1 THEN data_pesagem END) AS data_ini,"
            "    MAX(CASE WHEN rn_asc  = 1 THEN peso END)         AS peso_ini,"
            "    MAX(CASE WHEN rn_desc = 1 THEN data_pesagem END) AS data_fim,"
            "    MAX(CASE WHEN rn_desc = 1 THEN peso END)         AS peso_fim"
            "  FROM po GROUP BY animal_id"
            " ),"
            " gmd_calc AS ("
            "  SELECT animal_id, peso_fim AS peso_final,"
            "    DATEDIFF(data_fim, data_ini) AS dias,"
            "    CASE WHEN DATEDIFF(data_fim, data_ini) > 0"
            "      THEN ROUND((peso_fim - peso_ini) / DATEDIFF(data_fim, data_ini), 3)"
            "      ELSE NULL END AS gmd"
            "  FROM pu WHERE data_ini <> data_fim"
            " )"
            " SELECT a.id, a.brinco, a.sexo, a.raca, a.data_compra,"
            "  g.gmd, g.dias, g.peso_final"
            " FROM animais a"
            " LEFT JOIN gmd_calc g ON g.animal_id = a.id"
            " WHERE a.user_id = %s AND a.data_venda IS NULL AND a.deleted_at IS NULL"
            " ORDER BY LENGTH(a.brinco), a.brinco",
            (user_id, user_id)
        )
        return cursor.fetchall()


def get_animais_abaixo_gmd_medio(user_id, sexo=None, origem=None):
    """Animais ativos com GMD abaixo de (média - 2σ): outliers estatísticos do rebanho.

    `sexo` ('M'/'F') restringe o grupo usado para calcular média/desvio — mesma
    segregação de get_gmd_medio_rebanho, necessária para o dashboard não misturar
    as duas fontes de gmd_medio conforme existam ou não outliers.
    `origem='fazenda'` aplica o mesmo filtro de origem de get_gmd_medio_rebanho.
    """
    sexo_cond = " AND a.sexo = %s" if sexo in ('M', 'F') else ""
    origem_cond = _origem_cond(origem)
    params = [user_id] + ([sexo] if sexo in ('M', 'F') else [])
    with get_db_cursor() as cursor:
        cursor.execute(
            "WITH po AS ("
            "  SELECT p.animal_id, p.data_pesagem, p.peso,"
            "    ROW_NUMBER() OVER (PARTITION BY p.animal_id ORDER BY p.data_pesagem ASC)  AS rn_asc,"
            "    ROW_NUMBER() OVER (PARTITION BY p.animal_id ORDER BY p.data_pesagem DESC) AS rn_desc"
            "  FROM pesagens p"
            "  JOIN animais a ON a.id = p.animal_id"
            "    AND a.user_id = %s AND a.deleted_at IS NULL AND a.data_venda IS NULL"
            "    AND p.deleted_at IS NULL"
            f"    {sexo_cond}{origem_cond}"
            "),"
            " pu AS ("
            "  SELECT animal_id,"
            "    MAX(CASE WHEN rn_asc  = 1 THEN data_pesagem END) AS data_ini,"
            "    MAX(CASE WHEN rn_asc  = 1 THEN peso END)         AS peso_ini,"
            "    MAX(CASE WHEN rn_desc = 1 THEN data_pesagem END) AS data_fim,"
            "    MAX(CASE WHEN rn_desc = 1 THEN peso END)         AS peso_fim"
            "  FROM po GROUP BY animal_id"
            " ),"
            " gmd_calc AS ("
            "  SELECT animal_id,"
            "    CASE WHEN DATEDIFF(data_fim, data_ini) > 0"
            "      THEN (peso_fim - peso_ini) / DATEDIFF(data_fim, data_ini)"
            "      ELSE NULL END AS gmd"
            "  FROM pu WHERE data_ini <> data_fim"
            " ),"
            " agg AS ("
            "  SELECT AVG(gmd) AS gmd_media, STDDEV_POP(gmd) AS gmd_std"
            "  FROM gmd_calc WHERE gmd IS NOT NULL"
            " )"
            " SELECT gc.animal_id, a.brinco, gc.gmd, agg.gmd_media,"
            "  agg.gmd_std, (agg.gmd_media - 2 * agg.gmd_std) AS limite_inferior"
            " FROM gmd_calc gc"
            " CROSS JOIN agg"
            " JOIN animais a ON a.id = gc.animal_id"
            " WHERE gc.gmd IS NOT NULL AND gc.gmd < (agg.gmd_media - 2 * agg.gmd_std)"
            " ORDER BY gc.gmd ASC",
            tuple(params)
        )
        return cursor.fetchall()


def get_animais_abaixo_gmd_meta(user_id, gmd_meta):
    """Animais ativos com GMD abaixo de 75% da meta configurável da fazenda."""
    limite = float(gmd_meta) * 0.75
    with get_db_cursor() as cursor:
        cursor.execute(
            "WITH po AS ("
            "  SELECT p.animal_id, p.data_pesagem, p.peso,"
            "    ROW_NUMBER() OVER (PARTITION BY p.animal_id ORDER BY p.data_pesagem ASC)  AS rn_asc,"
            "    ROW_NUMBER() OVER (PARTITION BY p.animal_id ORDER BY p.data_pesagem DESC) AS rn_desc"
            "  FROM pesagens p"
            "  JOIN animais a ON a.id = p.animal_id"
            "    AND a.user_id = %s AND a.deleted_at IS NULL AND a.data_venda IS NULL"
            "    AND p.deleted_at IS NULL"
            "),"
            " pu AS ("
            "  SELECT animal_id,"
            "    MAX(CASE WHEN rn_asc  = 1 THEN data_pesagem END) AS data_ini,"
            "    MAX(CASE WHEN rn_asc  = 1 THEN peso END)         AS peso_ini,"
            "    MAX(CASE WHEN rn_desc = 1 THEN data_pesagem END) AS data_fim,"
            "    MAX(CASE WHEN rn_desc = 1 THEN peso END)         AS peso_fim"
            "  FROM po GROUP BY animal_id"
            " ),"
            " gmd_calc AS ("
            "  SELECT animal_id,"
            "    CASE WHEN DATEDIFF(data_fim, data_ini) > 0"
            "      THEN ROUND((peso_fim - peso_ini) / DATEDIFF(data_fim, data_ini), 3)"
            "      ELSE NULL END AS gmd"
            "  FROM pu WHERE data_ini <> data_fim"
            " )"
            " SELECT g.animal_id, a.brinco, g.gmd"
            " FROM gmd_calc g"
            " JOIN animais a ON a.id = g.animal_id"
            " WHERE g.gmd IS NOT NULL AND g.gmd < %s"
            " ORDER BY g.gmd ASC",
            (user_id, limite)
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
            "WITH po AS ("
            "  SELECT p.animal_id, p.data_pesagem, p.peso,"
            "    ROW_NUMBER() OVER (PARTITION BY p.animal_id ORDER BY p.data_pesagem ASC)  AS rn_asc,"
            "    ROW_NUMBER() OVER (PARTITION BY p.animal_id ORDER BY p.data_pesagem DESC) AS rn_desc"
            "  FROM pesagens p"
            "  JOIN animais filho ON filho.id = p.animal_id"
            "    AND (filho.pai_id = %s OR filho.mae_id = %s)"
            "    AND filho.user_id = %s AND filho.deleted_at IS NULL AND p.deleted_at IS NULL"
            "),"
            " pu AS ("
            "  SELECT animal_id,"
            "    MAX(CASE WHEN rn_asc  = 1 THEN data_pesagem END) AS data_ini,"
            "    MAX(CASE WHEN rn_asc  = 1 THEN peso END)         AS peso_ini,"
            "    MAX(CASE WHEN rn_desc = 1 THEN data_pesagem END) AS data_fim,"
            "    MAX(CASE WHEN rn_desc = 1 THEN peso END)         AS peso_fim"
            "  FROM po GROUP BY animal_id"
            " ),"
            " gmd_calc AS ("
            "  SELECT animal_id,"
            "    CASE WHEN DATEDIFF(data_fim, data_ini) > 0"
            "      THEN ROUND((peso_fim - peso_ini) / DATEDIFF(data_fim, data_ini), 3)"
            "      ELSE NULL END AS gmd"
            "  FROM pu WHERE data_ini <> data_fim"
            " )"
            " SELECT f.id, f.brinco, f.sexo, f.data_compra, g.gmd,"
            "  CASE WHEN f.pai_id = %s THEN 'pai' ELSE 'mae' END AS papel"
            " FROM animais f"
            " LEFT JOIN gmd_calc g ON g.animal_id = f.id"
            " WHERE (f.pai_id = %s OR f.mae_id = %s)"
            "   AND f.user_id = %s AND f.deleted_at IS NULL"
            " ORDER BY f.brinco",
            (animal_id, animal_id, user_id,   # CTE
             animal_id,                        # CASE WHEN papel
             animal_id, animal_id, user_id)    # WHERE
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
    """Ranking de touros por GMD médio dos filhos — inline, sem view."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "WITH po AS ("
            "  SELECT p.animal_id, p.data_pesagem, p.peso,"
            "    ROW_NUMBER() OVER (PARTITION BY p.animal_id ORDER BY p.data_pesagem ASC)  AS rn_asc,"
            "    ROW_NUMBER() OVER (PARTITION BY p.animal_id ORDER BY p.data_pesagem DESC) AS rn_desc"
            "  FROM pesagens p"
            "  JOIN animais filho ON filho.id = p.animal_id"
            "    AND filho.user_id = %s AND filho.pai_id IS NOT NULL"
            "    AND filho.deleted_at IS NULL AND p.deleted_at IS NULL"
            "),"
            " pu AS ("
            "  SELECT animal_id,"
            "    MAX(CASE WHEN rn_asc  = 1 THEN data_pesagem END) AS data_ini,"
            "    MAX(CASE WHEN rn_asc  = 1 THEN peso END)         AS peso_ini,"
            "    MAX(CASE WHEN rn_desc = 1 THEN data_pesagem END) AS data_fim,"
            "    MAX(CASE WHEN rn_desc = 1 THEN peso END)         AS peso_fim"
            "  FROM po GROUP BY animal_id"
            " ),"
            " gmd_filhos AS ("
            "  SELECT animal_id,"
            "    CASE WHEN DATEDIFF(data_fim, data_ini) > 0"
            "      THEN (peso_fim - peso_ini) / DATEDIFF(data_fim, data_ini)"
            "      ELSE NULL END AS gmd"
            "  FROM pu WHERE data_ini <> data_fim"
            " )"
            " SELECT t.id AS touro_id, t.brinco AS touro_brinco, t.raca AS touro_raca,"
            "  COUNT(f.id) AS qtd_filhos,"
            "  ROUND(AVG(gf.gmd), 3) AS gmd_medio_filhos"
            " FROM animais f"
            " JOIN animais t ON t.id = f.pai_id AND t.deleted_at IS NULL"
            " LEFT JOIN gmd_filhos gf ON gf.animal_id = f.id AND gf.gmd IS NOT NULL"
            " WHERE f.user_id = %s AND f.pai_id IS NOT NULL AND f.deleted_at IS NULL"
            " GROUP BY t.id, t.brinco, t.raca"
            " ORDER BY gmd_medio_filhos DESC",
            (user_id, user_id)
        )
        return cursor.fetchall()


# ---- MEDICACOES ----

def get_medicacoes_by_animal(animal_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id, animal_id, data_aplicacao, nome_medicamento, custo, observacoes "
            "FROM medicacoes WHERE animal_id = %s ORDER BY data_aplicacao DESC",
            (animal_id,)
        )
        return cursor.fetchall()


# ---- GRAFICOS ----

def get_contagem_por_sexo(user_id, origem=None):
    origem_cond = _origem_cond(origem, alias='')
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT sexo, COUNT(*) FROM animais "
            "WHERE user_id = %s AND data_venda IS NULL AND deleted_at IS NULL "
            f"{origem_cond} "
            "GROUP BY sexo",
            (user_id,)
        )
        return cursor.fetchall()


def get_pesos_atuais_rebanho(user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT p.peso "
            "FROM pesagens p "
            "INNER JOIN animais a ON p.animal_id = a.id "
            "WHERE a.user_id = %s AND a.data_venda IS NULL AND a.deleted_at IS NULL "
            "  AND p.deleted_at IS NULL "
            "  AND p.id = ("
            "    SELECT p2.id FROM pesagens p2 "
            "    WHERE p2.animal_id = p.animal_id AND p2.deleted_at IS NULL "
            "    ORDER BY p2.data_pesagem DESC, p2.id DESC LIMIT 1"
            "  )",
            (user_id,)
        )
        return cursor.fetchall()


# ---- ESCRITAS ATÔMICAS ----

def _inserir_animal(cursor, brinco, sexo, data_compra, preco_compra, peso_entrada, user_id,
                    data_nascimento=None, mae_id=None, pai_id=None, raca=None):
    """Insere animal e pesagem inicial (quando disponível) usando um cursor já aberto.

    Extraído de cadastrar_animal para ser reaproveitado por transações que
    precisam inserir o animal junto com outra escrita (ex.: bezerro do parto
    em reproducao_repository.registrar_parto_com_bezerro), sem abrir uma
    segunda transação/commit separado.
    """
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


def cadastrar_animal(brinco, sexo, data_compra, preco_compra, peso_entrada, user_id,
                     data_nascimento=None, mae_id=None, pai_id=None, raca=None):
    """Insere animal e pesagem inicial (quando disponível) na mesma transação. Retorna animal_id.

    Animais nascidos na fazenda passam data_compra=None e data_nascimento preenchida.
    Pesagem inicial só é inserida se peso_entrada for fornecido (> 0).
    """
    with get_db_cursor() as cursor:
        return _inserir_animal(cursor, brinco, sexo, data_compra, preco_compra, peso_entrada,
                               user_id, data_nascimento, mae_id, pai_id, raca)


def registrar_venda(animal_id, user_id, data_venda, preco_venda, peso_venda):
    """Atualiza venda e registra pesagem final na mesma transação. Retorna True se o animal pertence ao usuário."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id FROM animais WHERE id = %s AND user_id = %s AND deleted_at IS NULL",
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


def registrar_venda_lote(vendas, user_id, data_venda):
    """Registra venda de múltiplos animais em uma única transação.

    vendas: lista de (animal_id, peso_venda, preco_venda).
    Valida que todos os animal_ids pertencem ao user_id e ainda estão ativos.
    Retorna (vendidos, ids_invalidos).
    """
    if not vendas:
        return 0, []

    animal_ids = [v[0] for v in vendas]
    placeholders = ','.join(['%s'] * len(animal_ids))

    with get_db_cursor() as cursor:
        cursor.execute(
            f"SELECT id FROM animais WHERE id IN ({placeholders}) AND user_id = %s "
            "AND data_venda IS NULL AND deleted_at IS NULL",
            animal_ids + [user_id]
        )
        validos = {row[0] for row in cursor.fetchall()}
        invalidos = [aid for aid in animal_ids if aid not in validos]

        vendas_validas = [(aid, peso_venda, preco_venda) for aid, peso_venda, preco_venda in vendas if aid in validos]
        if vendas_validas:
            cursor.executemany(
                "UPDATE animais SET data_venda = %s, preco_venda = %s WHERE id = %s",
                [(data_venda, preco_venda, aid) for aid, peso_venda, preco_venda in vendas_validas]
            )
            cursor.executemany(
                "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)",
                [(aid, data_venda, peso_venda) for aid, peso_venda, preco_venda in vendas_validas]
            )

    return len(vendas_validas), invalidos


def registrar_pesagem(animal_id, user_id, data_pesagem, peso):
    """Valida propriedade e insere pesagem na mesma transação. Retorna True se bem-sucedido."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id FROM animais WHERE id = %s AND user_id = %s AND deleted_at IS NULL",
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
            "SELECT id FROM animais WHERE id = %s AND user_id = %s AND deleted_at IS NULL",
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


def insert_medicacao_lote(animal_ids, data_aplicacao, nome, custo, obs, user_id):
    """Insere medicação em múltiplos animais na mesma transação.

    Apenas animais ativos pertencentes ao user_id são processados.
    """
    if not animal_ids:
        return
    with get_db_cursor() as cursor:
        placeholders = ','.join(['%s'] * len(animal_ids))
        cursor.execute(
            f"SELECT id FROM animais WHERE id IN ({placeholders}) AND user_id = %s AND deleted_at IS NULL",
            list(animal_ids) + [user_id]
        )
        ids_validos = {row[0] for row in cursor.fetchall()}
        animal_ids = [aid for aid in animal_ids if int(aid) in ids_validos]
        if not animal_ids:
            return
        cursor.executemany(
            "INSERT INTO medicacoes (animal_id, data_aplicacao, nome_medicamento, custo, observacoes) "
            "VALUES (%s, %s, %s, %s, %s)",
            [(aid, data_aplicacao, nome, custo, obs) for aid in animal_ids]
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

        cursor.executemany(
            "INSERT INTO animais (brinco, sexo, raca, data_compra, preco_compra, user_id, lote_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [(brinco, sexo, raca or None, data_compra, custo_animal, user_id, lote_id)
             for brinco, sexo, peso, custo_animal in animais_data]
        )

        # brinco é único por usuário — reconsulta os ids recém-criados para
        # montar as pesagens iniciais sem depender de lastrowid por linha
        # (que o executemany não fornece individualmente).
        brincos = [brinco for brinco, sexo, peso, custo_animal in animais_data]
        placeholders = ','.join(['%s'] * len(brincos))
        cursor.execute(
            f"SELECT id, brinco FROM animais WHERE lote_id = %s AND brinco IN ({placeholders})",
            [lote_id] + brincos
        )
        id_por_brinco = {brinco: aid for aid, brinco in cursor.fetchall()}

        cursor.executemany(
            "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)",
            [(id_por_brinco[brinco], data_compra, peso) for brinco, sexo, peso, custo_animal in animais_data]
        )
        return lote_id
