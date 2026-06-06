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
    """Detalhes de custos operacionais de um ano específico."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT data_custo, categoria, tipo_custo, valor, descricao "
            "FROM custos_operacionais "
            "WHERE user_id = %s AND YEAR(data_custo) = %s AND deleted_at IS NULL "
            "ORDER BY data_custo DESC",
            (user_id, ano)
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
