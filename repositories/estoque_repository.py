from db_config import get_db_cursor


def get_produtos(user_id):
    """Retorna todos os produtos do usuário com saldo atual (via vw_saldo_estoque)."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT produto_id, user_id, nome, unidade, categoria, estoque_minimo, "
            "    total_entradas, total_saidas, saldo_atual, abaixo_minimo, "
            "    proxima_validade, tem_vencido "
            "FROM vw_saldo_estoque WHERE user_id = %s ORDER BY nome ASC",
            (user_id,)
        )
        return cursor.fetchall()


def insert_produto(user_id, nome, unidade, categoria, estoque_minimo):
    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO estoque_produtos (user_id, nome, unidade, categoria, estoque_minimo) "
            "VALUES (%s, %s, %s, %s, %s)",
            (user_id, nome, unidade, categoria, estoque_minimo or 0)
        )
        return cursor.lastrowid


def get_produto_by_id(produto_id, user_id):
    """Retorna dados do produto com saldo atual (via view). Valida propriedade."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT produto_id, user_id, nome, unidade, categoria, estoque_minimo, "
            "    total_entradas, total_saidas, saldo_atual, abaixo_minimo, "
            "    proxima_validade, tem_vencido "
            "FROM vw_saldo_estoque WHERE produto_id = %s AND user_id = %s",
            (produto_id, user_id)
        )
        return cursor.fetchone()


def get_movimentacoes_by_produto(produto_id, user_id):
    """Histórico de movimentações do produto, validando propriedade via JOIN."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT m.id, m.tipo, m.quantidade, m.custo_unitario, m.motivo, m.data_mov, "
            "    m.lote_fabricante, m.data_validade "
            "FROM estoque_movimentacoes m "
            "JOIN estoque_produtos p ON m.produto_id = p.id "
            "WHERE m.produto_id = %s AND p.user_id = %s "
            "ORDER BY m.data_mov DESC, m.id DESC",
            (produto_id, user_id)
        )
        return cursor.fetchall()


def get_saldo_atual(produto_id, user_id):
    """Retorna somente o saldo atual do produto (para validação de saída)."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT saldo_atual FROM vw_saldo_estoque "
            "WHERE produto_id = %s AND user_id = %s",
            (produto_id, user_id)
        )
        row = cursor.fetchone()
        return float(row[0]) if row else 0.0


def insert_movimentacao(user_id, produto_id, tipo, quantidade, custo_unitario, motivo, data_mov,
                        lote_fabricante=None, data_validade=None):
    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO estoque_movimentacoes "
            "(user_id, produto_id, tipo, quantidade, custo_unitario, motivo, data_mov, "
            " lote_fabricante, data_validade) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (user_id, produto_id, tipo,
             quantidade, custo_unitario or None, motivo or None, data_mov,
             lote_fabricante or None, data_validade or None)
        )
        return cursor.lastrowid


def get_vencendo_em_dias(user_id, dias=30):
    """Produtos com data_validade nas próximas `dias` dias ou já vencidos."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT produto_id, nome, proxima_validade, tem_vencido "
            "FROM vw_saldo_estoque "
            "WHERE user_id = %s AND proxima_validade IS NOT NULL "
            "AND proxima_validade <= DATE_ADD(CURDATE(), INTERVAL %s DAY) "
            "ORDER BY proxima_validade ASC",
            (user_id, dias)
        )
        return cursor.fetchall()
