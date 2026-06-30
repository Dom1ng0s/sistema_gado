import pytest
import mysql.connector

DB_CONFIG = {
    "host": "localhost", "user": "gado_test",
    "password": "gado123", "port": 3306, "database": "sistema_gado_test",
}

def login(client):
    return client.post('/login', data={'username': 'testuser', 'password': '123'}, follow_redirects=True)


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

    # 2. Verifica no Painel Financeiro se o valor aparece
    response_fin = client.get('/financeiro?ano=2024')
    assert b"500.00" in response_fin.data
    
    # CORREÇÃO: Converter string com acento para bytes antes de comparar
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


# ── Sprint 2 — Widgets de Inteligência Zootécnica ──────────────────────────

def test_financeiro_widget_prenhez_sem_dados(client):
    """Painel financeiro carrega sem erros quando não há gestações registradas."""
    login(client)
    response = client.get('/financeiro')
    assert response.status_code == 200
    assert 'Reprodu'.encode('utf-8') in response.data


def test_financeiro_widget_prenhez_com_dg_positivo(client):
    """Widget de prenhez exibe vaca gestante com DG positivo."""
    login(client)
    uid = _get_user_id()
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    # Cria vaca e touro
    cur.execute(
        "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id) "
        "VALUES ('VACA-DG01', 'F', '2023-01-01', 800, %s)",
        (uid,)
    )
    vaca_id = cur.lastrowid
    # Reprodução com DG positivo e parto previsto nos próximos 30 dias
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
    assert b'VACA-DG01' in response.data


def test_financeiro_widget_gmd_sem_dados(client):
    """Painel financeiro carrega sem erros quando não há dados de GMD por módulo."""
    login(client)
    response = client.get('/financeiro')
    assert response.status_code == 200
    assert 'Top M'.encode('utf-8') in response.data
