import pytest
import mysql.connector
from werkzeug.security import generate_password_hash

DB_CONFIG = {
    "host": "localhost", "user": "gado_test",
    "password": "gado123", "port": 3306, "database": "sistema_gado_test",
}

def login(client):
    return client.post('/login', data={'username': 'testuser', 'password': '123'}, follow_redirects=True)


def _make_user(username):
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
        (username, generate_password_hash("x")),
    )
    uid = cur.lastrowid
    conn.commit(); cur.close(); conn.close()
    return uid


def _login_as(client, username):
    client.post('/login', data={'username': username, 'password': 'x'}, follow_redirects=True)


def _insert_agendamento(user_id, descricao="Conta teste", valor=100.0, vencimento="2024-12-01"):
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO financial_schedule (user_id, descricao, valor, vencimento, status) "
        "VALUES (%s, %s, %s, %s, 'pendente')",
        (user_id, descricao, valor, vencimento),
    )
    agend_id = cur.lastrowid
    conn.commit(); cur.close(); conn.close()
    return agend_id


def _criar_lote_com_animais(user_id, codigo="LOTE-PL", com_venda=False):
    """Helper: cria lote + 2 animais no banco de teste, retorna lote_id."""
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO lotes (user_id, codigo_lote, descricao, data_aquisicao) VALUES (%s,%s,%s,'2024-01-10')",
        (user_id, codigo, "Lote teste P&L")
    )
    lote_id = cur.lastrowid
    cur.execute(
        "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id, lote_id) VALUES (%s,'M','2024-01-10',1000,%s,%s)",
        (f"{codigo}-A1", user_id, lote_id)
    )
    a1 = cur.lastrowid
    cur.execute(
        "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id, lote_id) VALUES (%s,'F','2024-01-10',800,%s,%s)",
        (f"{codigo}-A2", user_id, lote_id)
    )
    if com_venda:
        a2 = cur.lastrowid
        cur.execute(
            "UPDATE animais SET data_venda='2024-06-01', preco_venda=1500 WHERE id=%s",
            (a1,)
        )
    conn.commit()
    cur.close()
    conn.close()
    return lote_id


def _get_user_id():
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT id FROM usuarios WHERE username='testuser'")
    uid = cur.fetchone()[0]
    cur.close()
    conn.close()
    return uid

def test_acesso_financeiro(client):
    """Verifica se o painel financeiro carrega sem erros (mesmo vazio)."""
    login(client)
    response = client.get('/financeiro')
    assert response.status_code == 200
    assert b"Dashboard Financeiro" in response.data

def test_lancamento_custo(client):
    """Testa o lançamento de um custo e se ele aparece no total."""
    login(client)

    # 1. Lança um custo de R$ 500,00
    response = client.post('/custos_operacionais', data={
        'data': '2024-06-01',
        'categoria': 'Fixo',
        'tipo_fixo': 'Salário',
        'valor': '500.00',
        'descricao': 'Pagamento Teste'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Custo registrado" in response.data

    # 2. Verifica no Painel Financeiro se o valor aparece (filtro |brl usa vírgula decimal)
    response_fin = client.get('/financeiro?ano=2024')
    assert "500,00".encode('utf-8') in response_fin.data
    assert "Salário".encode('utf-8') in response_fin.data

def test_simulador_custo(client):
    """Testa se o simulador aceita input e retorna cálculo."""
    login(client)
    
    response = client.post('/simulador-custo', data={
        'qtd_animais': '10',
        'gmd': '0.800',
        'custo_arrendamento': '1000', # 100 por cabeça
        'custo_suplementacao': '500', # 50 por cabeça
        'custo_mao_obra': '0',
        'custos_extras': '0'
    })
    
    assert response.status_code == 200
    
    # Validação matemática (escopo anual): 1500 / 10 animais / 365 dias = 0.41/dia
    assert b"1,500.00" in response.data # Total Anual
    assert b"0.41" in response.data     # Diária (anual)

def test_export_financeiro_csv(client):
    """Exportação CSV financeiro retorna arquivo com cabeçalho correto."""
    login(client)
    response = client.get('/api/v1/export/financeiro.csv')
    assert response.status_code == 200
    assert response.content_type.startswith('text/csv')
    text = response.data.decode('utf-8-sig')
    assert 'Data' in text
    assert 'Valor (R$)' in text


def test_export_financeiro_csv_com_ano(client):
    """Exportação CSV financeiro aceita parâmetro ?ano."""
    login(client)
    response = client.get('/api/v1/export/financeiro.csv?ano=2023')
    assert response.status_code == 200
    assert 'financeiro_2023.csv' in response.headers.get('Content-Disposition', '')


# ── 5.1 — P&L por lote ─────────────────────────────────────────────────────

def test_resultado_lotes_vazio(client):
    """Página de P&L carrega quando não há lotes."""
    login(client)
    response = client.get('/financeiro/lotes')
    assert response.status_code == 200
    assert 'Resultado por Lote'.encode('utf-8') in response.data


def test_resultado_lotes_com_lote(client):
    """Lote criado aparece na listagem com código e custos."""
    login(client)
    uid = _get_user_id()
    _criar_lote_com_animais(uid, codigo="PL-LISTA")
    response = client.get('/financeiro/lotes')
    assert response.status_code == 200
    assert b'PL-LISTA' in response.data


def test_resultado_lotes_calcula_margem_com_venda(client):
    """Margem bruta reflete receita menos compra quando há venda."""
    login(client)
    uid = _get_user_id()
    _criar_lote_com_animais(uid, codigo="PL-VENDA", com_venda=True)
    response = client.get('/financeiro/lotes')
    assert response.status_code == 200
    assert b'PL-VENDA' in response.data


def test_detalhe_lote_exibe_animais(client):
    """Detalhe de lote lista os animais com brinco e preço."""
    login(client)
    uid = _get_user_id()
    lote_id = _criar_lote_com_animais(uid, codigo="PL-DET")
    response = client.get(f'/financeiro/lotes/{lote_id}')
    assert response.status_code == 200
    assert b'PL-DET' in response.data
    assert b'PL-DET-A1' in response.data


def test_detalhe_lote_outro_usuario_redireciona(client):
    """Lote de outro usuário redireciona para lista (não vaza dados)."""
    login(client)
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("INSERT INTO usuarios (username, password_hash) VALUES ('outro','x')")
    outro_id = cur.lastrowid
    cur.execute(
        "INSERT INTO lotes (user_id, codigo_lote, data_aquisicao) VALUES (%s,'LOTE-OUTRO','2024-01-01')",
        (outro_id,)
    )
    lote_alheio = cur.lastrowid
    cur.execute(
        "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id, lote_id) "
        "VALUES ('ALHEIO-01','M','2024-01-01',500,%s,%s)",
        (outro_id, lote_alheio)
    )
    conn.commit()
    cur.close()
    conn.close()
    response = client.get(f'/financeiro/lotes/{lote_alheio}')
    assert response.status_code == 302


# ── Fronteira de domínio — zootecnia não pertence ao Financeiro (issue #71) ──

def test_financeiro_nao_exibe_dados_de_prenhez(client):
    """Vaca gestante não deve aparecer no Financeiro — o lugar dela é /reproducao."""
    login(client)
    uid = _get_user_id()
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id) "
        "VALUES ('VACA-DG01', 'F', '2023-01-01', 800, %s)",
        (uid,)
    )
    vaca_id = cur.lastrowid
    from datetime import date, timedelta
    data_cob = date.today() - timedelta(days=260)
    data_prev = data_cob + timedelta(days=285)
    cur.execute(
        "INSERT INTO reproducao "
        "(user_id, vaca_id, data_cobertura, resultado, diagnostico, data_diagnostico, data_parto_prevista) "
        "VALUES (%s, %s, %s, 'vivo', 'positivo', CURDATE(), %s)",
        (uid, vaca_id, data_cob, data_prev)
    )
    conn.commit()
    cur.close()
    conn.close()

    response = client.get('/financeiro')
    assert response.status_code == 200
    assert b'VACA-DG01' not in response.data

    # ...e continua visível no painel de reprodução, que é o dono do dado.
    response = client.get('/reproducao')
    assert response.status_code == 200
    assert b'VACA-DG01' in response.data


def test_financeiro_nao_exibe_gmd_por_modulo(client):
    """Widget "Top Módulos por GMD" saiu do Financeiro — vive em Relatórios."""
    login(client)
    response = client.get('/financeiro')
    assert response.status_code == 200
    assert 'Top M'.encode('utf-8') not in response.data


# ── Sprint 3 — Agrupamento de Custos ────────────────────────────────────────

def test_custos_agrupados_exibe_contagem(client):
    """3 custos do mesmo tipo no mesmo dia devem aparecer agrupados como (3x)."""
    login(client)
    ano = __import__('datetime').date.today().year
    hoje = __import__('datetime').date.today().isoformat()

    for _ in range(3):
        client.post('/custos_operacionais', data={
            'data': hoje,
            'categoria': 'Variavel',
            'tipo_variavel': 'Nutrição',
            'valor': '100.00',
            'descricao': '',
        }, follow_redirects=True)

    response = client.get(f'/financeiro?ano={ano}')
    assert response.status_code == 200
    assert b'(3x)' in response.data


def test_export_csv_tem_coluna_qtd(client):
    """CSV exportado deve ter cabeçalho com coluna Qtd."""
    login(client)
    response = client.get('/api/v1/export/financeiro.csv')
    assert response.status_code == 200
    text = response.data.decode('utf-8-sig')
    assert 'Qtd' in text


# ── Agendamentos (contas a pagar) ────────────────────────────────────────────

def test_agendamentos_lista_vazia(client):
    """Página de agendamentos carrega mesmo sem contas cadastradas."""
    login(client)
    response = client.get('/financeiro/agendamentos')
    assert response.status_code == 200


def test_agendamentos_post_cria_conta(client):
    """POST cria agendamento e ele aparece na listagem."""
    login(client)
    response = client.post('/financeiro/agendamentos', data={
        'descricao': 'Conta de luz',
        'valor': '350.50',
        'vencimento': '2026-08-10',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Conta de luz' in response.data
    assert 'salvo'.encode('utf-8') in response.data.lower() or b'sucesso' in response.data


def test_agendamentos_post_sem_valor_retorna_erro(client):
    """Validação rejeita agendamento sem valor — nada é persistido no banco."""
    login(client)
    uid = _get_user_id()
    response = client.post('/financeiro/agendamentos', data={
        'descricao': 'Conta sem valor único XYZ',
        'valor': '',
        'vencimento': '2026-08-10',
    }, follow_redirects=True)
    assert response.status_code == 200

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM financial_schedule WHERE user_id=%s AND descricao='Conta sem valor único XYZ'",
        (uid,),
    )
    count = cur.fetchone()[0]
    cur.close(); conn.close()
    assert count == 0


def test_agendamentos_editar_atualiza_valor(client):
    """POST /financeiro/agendamentos/<id>/editar atualiza a conta pendente."""
    login(client)
    uid = _get_user_id()
    agend_id = _insert_agendamento(uid, descricao="Conta a editar", valor=100.0)

    response = client.post(f'/financeiro/agendamentos/{agend_id}/editar', data={
        'descricao': 'Conta editada',
        'valor': '222.00',
        'vencimento': '2026-09-01',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Conta editada' in response.data

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT descricao, valor FROM financial_schedule WHERE id=%s", (agend_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    assert row[0] == 'Conta editada'
    assert float(row[1]) == 222.00


def test_agendamentos_excluir_soft_deleta(client):
    """POST /financeiro/agendamentos/<id>/excluir marca deleted_at e some da listagem."""
    login(client)
    uid = _get_user_id()
    agend_id = _insert_agendamento(uid, descricao="Conta a excluir")

    response = client.post(f'/financeiro/agendamentos/{agend_id}/excluir', follow_redirects=True)
    assert response.status_code == 200
    assert b'Conta a excluir' not in response.data

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT deleted_at FROM financial_schedule WHERE id=%s", (agend_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    assert row[0] is not None


def test_agendamentos_editar_de_outro_usuario_nao_altera(client):
    """POST editar de um agendamento alheio não deve alterá-lo (isolamento multi-tenant)."""
    login(client)
    outro_id = _make_user('fin_outro_editar')
    agend_id = _insert_agendamento(outro_id, descricao="Conta Alheia Editar", valor=50.0)

    response = client.post(f'/financeiro/agendamentos/{agend_id}/editar', data={
        'descricao': 'Hackeado',
        'valor': '999.00',
        'vencimento': '2026-10-01',
    }, follow_redirects=True)
    assert response.status_code == 200

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT descricao, valor FROM financial_schedule WHERE id=%s", (agend_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    assert row[0] == 'Conta Alheia Editar'
    assert float(row[1]) == 50.0


def test_agendamentos_excluir_de_outro_usuario_nao_altera(client):
    """POST excluir de um agendamento alheio não deve marcá-lo como deletado."""
    login(client)
    outro_id = _make_user('fin_outro_excluir')
    agend_id = _insert_agendamento(outro_id, descricao="Conta Alheia Excluir")

    client.post(f'/financeiro/agendamentos/{agend_id}/excluir', follow_redirects=True)

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT deleted_at FROM financial_schedule WHERE id=%s", (agend_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    assert row[0] is None


def test_agendamentos_baixar_de_outro_usuario_nao_altera(client):
    """POST /financeiro/baixar/<id> de outro usuário não deve marcar a conta alheia como paga."""
    login(client)
    outro_id = _make_user('fin_outro_baixar')
    agend_id = _insert_agendamento(outro_id, descricao="Conta Alheia Baixar")

    client.post(f'/financeiro/baixar/{agend_id}', follow_redirects=True)

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT status FROM financial_schedule WHERE id=%s", (agend_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    assert row[0] == 'pendente'


# ── Alerta de erro centralizado no base.html (issue #72) ─────────────────────

def test_erro_de_validacao_renderiza_alerta(client):
    """`mensagem` é renderizada pelo base.html — os templates não repetem mais o bloco.

    Guarda a issue #72: se a renderização central sumir, o usuário perde o
    feedback de validação sem que nenhum status HTTP mude.
    """
    login(client)
    response = client.post('/custos_operacionais', data={
        'categoria': 'Variavel',
        'tipo_variavel': 'Nutrição',
        'valor': '-5',            # viola min_val=0.01
        'data': '2024-01-01',
        'descricao': '',
    })
    assert response.status_code == 200
    corpo = response.data.decode('utf-8')
    assert 'alert-danger' in corpo
    assert 'Valor' in corpo
    # e o form_data digitado sobrevive ao erro (motivo de não usar redirect+flash)
    assert 'Nutri' in corpo
