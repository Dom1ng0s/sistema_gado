from db_config import get_db_cursor
from datetime import date


# ---- REBANHO ----

def get_valor_rebanho(user_id):
    """Soma de preco_compra dos animais ativos, excluindo deletados e vendidos."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT SUM(preco_compra) FROM animais "
            "WHERE user_id = %s AND data_venda IS NULL AND deleted_at IS NULL",
            (user_id,)
        )
        res = cursor.fetchone()
        return float(res[0]) if res and res[0] else 0.0


# ---- FLUXO DE CAIXA ----

def get_fluxo_caixa(user_id):
    """Histórico anual de entradas/saídas da view v_fluxo_caixa."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT ano, total_entradas, total_compras, total_med, total_ops "
            "FROM v_fluxo_caixa WHERE user_id = %s ORDER BY ano DESC",
            (user_id,)
        )
        return cursor.fetchall()


# ---- CUSTOS OPERACIONAIS ----

def get_custos_por_tipo_trimestre(user_id, data_limite):
    """Soma por tipo_custo a partir de data_limite, excluindo soft-deleted."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT tipo_custo, SUM(valor) FROM custos_operacionais "
            "WHERE user_id = %s AND data_custo >= %s AND deleted_at IS NULL "
            "GROUP BY tipo_custo",
            (user_id, data_limite)
        )
        return cursor.fetchall()


def get_custos_por_ano(user_id, ano):
    """Custos operacionais + medicações/vacinas de um ano, ordenados por data."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "(SELECT data_custo, categoria, tipo_custo, valor, descricao "
            " FROM custos_operacionais "
            " WHERE user_id = %s AND YEAR(data_custo) = %s AND deleted_at IS NULL) "
            "UNION ALL "
            "(SELECT m.data_aplicacao, 'Sanitário', m.nome_medicamento, m.custo, m.observacoes "
            " FROM medicacoes m JOIN animais a ON m.animal_id = a.id "
            " WHERE a.user_id = %s AND YEAR(m.data_aplicacao) = %s "
            "   AND m.deleted_at IS NULL AND a.deleted_at IS NULL) "
            "ORDER BY 1 DESC",
            (user_id, ano, user_id, ano)
        )
        return cursor.fetchall()


def insert_custo_operacional(user_id, categoria, tipo_custo, valor, data_custo, descricao):
    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO custos_operacionais "
            "(user_id, categoria, tipo_custo, valor, data_custo, descricao) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, categoria, tipo_custo, valor, data_custo, descricao)
        )


def get_categorias_custo():
    """Centros de custo da tabela de referência compartilhada (sem filtro user_id)."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT nome, categoria FROM cost_centers ORDER BY nome")
        return cursor.fetchall()


# ---- AGENDAMENTOS FINANCEIROS ----

def get_agendamentos(user_id):
    """Agendamentos não deletados ordenados por vencimento."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id, descricao, valor, vencimento, status "
            "FROM financial_schedule "
            "WHERE user_id = %s AND deleted_at IS NULL "
            "ORDER BY vencimento ASC",
            (user_id,)
        )
        return cursor.fetchall()


def insert_agendamento(user_id, descricao, valor, vencimento):
    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO financial_schedule (user_id, descricao, valor, vencimento, status) "
            "VALUES (%s, %s, %s, %s, 'pendente')",
            (user_id, descricao, valor, vencimento)
        )


# ---- RESULTADO POR LOTE (P&L) ----

def get_resultado_lotes(user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT lote_id, codigo_lote, descricao, data_aquisicao, "
            "total_animais, custo_aquisicao, receita_vendas, "
            "custo_medicacoes, animais_vendidos, margem_bruta "
            "FROM vw_resultado_lote "
            "WHERE user_id = %s ORDER BY data_aquisicao DESC",
            (user_id,)
        )
        return cursor.fetchall()


def get_resultado_lote_by_id(lote_id, user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT lote_id, codigo_lote, descricao, data_aquisicao, "
            "total_animais, custo_aquisicao, receita_vendas, "
            "custo_medicacoes, animais_vendidos, margem_bruta "
            "FROM vw_resultado_lote "
            "WHERE lote_id = %s AND user_id = %s",
            (lote_id, user_id)
        )
        return cursor.fetchone()


def get_animais_por_lote(lote_id, user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT a.brinco, a.sexo, a.raca, a.data_compra, a.preco_compra, "
            "a.data_venda, a.preco_venda, "
            "COALESCE(m.custo_med, 0) AS custo_med, "
            "COALESCE(g.gmd, 0) AS gmd, "
            "COALESCE(g.peso_final, 0) AS peso_atual "
            "FROM animais a "
            "LEFT JOIN (SELECT animal_id, SUM(custo) AS custo_med "
            "           FROM medicacoes WHERE deleted_at IS NULL GROUP BY animal_id) m "
            "  ON m.animal_id = a.id "
            "LEFT JOIN v_gmd_analitico g ON g.animal_id = a.id "
            "WHERE a.lote_id = %s AND a.user_id = %s AND a.deleted_at IS NULL "
            "ORDER BY a.brinco ASC",
            (lote_id, user_id)
        )
        return cursor.fetchall()


def baixar_agendamento(id_agendamento, user_id):
    """
    Operação atômica: verifica se o agendamento é pendente e pertence ao usuário,
    marca como pago e registra o custo operacional correspondente.
    Retorna True se processado, False se não encontrado ou já pago.
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT descricao, valor FROM financial_schedule "
            "WHERE id = %s AND user_id = %s AND status = 'pendente'",
            (id_agendamento, user_id)
        )
        item = cursor.fetchone()
        if not item:
            return False
        descricao_origem, valor = item
        cursor.execute(
            "UPDATE financial_schedule SET status = 'pago' WHERE id = %s",
            (id_agendamento,)
        )
        cursor.execute(
            "INSERT INTO custos_operacionais "
            "(user_id, categoria, tipo_custo, valor, data_custo, descricao) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, 'Financeiro', 'Agendamento', valor, date.today(),
             descricao_origem + " (Via Agendamento)")
        )
        return True
