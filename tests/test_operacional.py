import pytest

import db_config as dbc

# Helper para logar antes de cada teste
def login(client):
    return client.post('/login', data={'username': 'testuser', 'password': '123'}, follow_redirects=True)


def _fetch_one(sql, params=()):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

def test_cadastro_animal(client):
    """Testa se é possível cadastrar um animal corretamente."""
    login(client)
    
    # 1. Faz o POST do cadastro
    response = client.post('/cadastro', data={
        'brinco': 'TEST-01',
        'sexo': 'M',
        'data_compra': '2024-01-01',
        'peso_compra': '300.00',
        'valor_arroba': '250.00'
    }, follow_redirects=True)

    assert response.status_code == 200
    # CORREÇÃO: Verifica a mensagem de sucesso na própria página de cadastro
    assert b"cadastrado" in response.data 

    # 2. Navega explicitamente para o Painel para validar a lista
    response_painel = client.get('/painel')
    assert response_painel.status_code == 200
    assert b"TEST-01" in response_painel.data
    assert b"Ativo" in response_painel.data

def test_validacao_cadastro_duplicado(client):
    """Impede cadastro de dois animais com mesmo brinco para o mesmo usuário."""
    login(client)
    
    # Primeiro cadastro
    client.post('/cadastro', data={
        'brinco': 'DUPLICADO', 'sexo': 'F', 'data_compra': '2024-01-01',
        'peso_compra': '300', 'valor_arroba': '250'
    })
    
    # Segundo cadastro (Tentativa de erro)
    response = client.post('/cadastro', data={
        'brinco': 'DUPLICADO', 'sexo': 'F', 'data_compra': '2024-01-01',
        'peso_compra': '300', 'valor_arroba': '250'
    }, follow_redirects=True)

    # Verifica se a mensagem de erro aparece
    assert b"Erro" in response.data or b"existe" in response.data

def test_venda_animal(client):
    """Cadastra e Vende um animal, verificando a baixa de estoque."""
    login(client)
    
    # 1. Cadastra animal para venda
    client.post('/cadastro', data={
        'brinco': 'VENDIDO-01', 'sexo': 'M', 'data_compra': '2024-02-01',
        'peso_compra': '500', 'valor_arroba': '300'
    })

    # 2. Descobre o ID do animal recém-criado (o banco de teste é compartilhado
    # entre todo o módulo pytest, então o ID não é previsível/hardcodável)
    row = _fetch_one(
        "SELECT id FROM animais WHERE brinco='VENDIDO-01' AND deleted_at IS NULL"
    )
    assert row is not None
    animal_id = row[0]

    response = client.post(f'/vender/{animal_id}', data={
        'data_venda': '2024-05-01',
        'peso_venda': '550',
        'valor_arroba': '310'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    # 3. Verifica no painel se está como VENDIDO
    response_painel = client.get('/painel?status=vendidos')
    assert b"VENDIDO-01" in response_painel.data
    # O status visual no HTML é uma tag <span class="tag-vendido">VENDIDO</span>
    assert b"VENDIDO" in response_painel.data


def test_cadastro_animal_nascido_na_fazenda(client):
    """Cadastra animal nascido na fazenda (sem data_compra) usando data_nascimento."""
    login(client)
    response = client.post('/cadastro', data={
        'brinco': 'NASC-01',
        'sexo': 'F',
        'data_nascimento': '2024-03-15',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'cadastrado' in response.data


def test_cadastro_animal_sem_data_alguma(client):
    """POST sem data_compra nem data_nascimento retorna erro 400."""
    login(client)
    response = client.post('/cadastro', data={
        'brinco': 'SEM-DATA',
        'sexo': 'M',
    }, follow_redirects=True)
    assert response.status_code == 400


def test_pesagem_lote_get(client):
    """Página de pesagem em lote carrega corretamente."""
    login(client)
    response = client.get('/pesagem-lote')
    assert response.status_code == 200
    assert 'Pesagem' in response.data.decode('utf-8')


def test_pesagem_lote_sem_animais_selecionados(client):
    """POST sem animais retorna erro 400."""
    login(client)
    response = client.post('/pesagem-lote', data={
        'data_pesagem': '2024-06-01',
        'animal_ids[]': [],
        'pesos[]': [],
    }, follow_redirects=True)
    assert response.status_code == 400


def test_pesagem_lote_sucesso(client):
    """Cadastra animal e registra pesagem em lote com sucesso."""
    login(client)

    client.post('/cadastro', data={
        'brinco': 'PL-01', 'sexo': 'M',
        'data_compra': '2024-01-01',
        'peso_compra': '300', 'valor_arroba': '250',
    })

    # Busca o ID do animal via DB usando o repositório (sem depender de ID fixo)
    import db_config as dbc
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT a.id FROM animais a JOIN usuarios u ON a.user_id = u.id "
        "WHERE u.username = 'testuser' AND a.brinco = 'PL-01'"
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    assert row is not None, "Animal PL-01 não foi criado"
    animal_id = row[0]

    response = client.post('/pesagem-lote', data={
        'data_pesagem': '2024-06-01',
        'animal_ids[]': [str(animal_id)],
        'pesos[]': ['320.5'],
    }, follow_redirects=True)

    assert response.status_code == 200
    assert 'registrada' in response.data.decode('utf-8')

def test_export_animais_csv(client):
    """Exportação CSV de animais retorna arquivo com cabeçalho correto."""
    login(client)
    response = client.get('/api/v1/export/animais.csv')
    assert response.status_code == 200
    assert response.content_type.startswith('text/csv')
    text = response.data.decode('utf-8-sig')
    assert 'Brinco' in text
    assert 'GMD' in text


# ── Testes 4.4: Raça do animal ────────────────────────────────────────────

def test_cadastro_animal_com_raca(client):
    """Cadastro com raça predefinida persiste o campo."""
    login(client)
    response = client.post('/cadastro', data={
        'brinco': 'RACA-01', 'sexo': 'M', 'raca': 'Nelore',
        'data_compra': '2024-03-01',
        'peso_compra': '280', 'valor_arroba': '240',
    }, follow_redirects=True)
    assert response.status_code == 200

    import db_config as dbc
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT raca FROM animais a JOIN usuarios u ON a.user_id = u.id "
        "WHERE u.username = 'testuser' AND a.brinco = 'RACA-01'"
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    assert row is not None
    assert row[0] == 'Nelore'


def test_cadastro_animal_com_raca_outra(client):
    """Cadastro com opção Outra usa o campo raca_outra."""
    login(client)
    response = client.post('/cadastro', data={
        'brinco': 'RACA-02', 'sexo': 'F', 'raca': '__outra__',
        'raca_outra': 'Canchim',
        'data_compra': '2024-03-01',
        'peso_compra': '200', 'valor_arroba': '240',
    }, follow_redirects=True)
    assert response.status_code == 200

    import db_config as dbc
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT raca FROM animais a JOIN usuarios u ON a.user_id = u.id "
        "WHERE u.username = 'testuser' AND a.brinco = 'RACA-02'"
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    assert row is not None
    assert row[0] == 'Canchim'


def test_painel_filtro_raca(client):
    """Filtro por raça retorna somente animais da raça solicitada."""
    login(client)
    # Cadastra dois animais com raças distintas
    client.post('/cadastro', data={
        'brinco': 'FILT-N01', 'sexo': 'M', 'raca': 'Nelore',
        'data_compra': '2024-03-01', 'peso_compra': '300', 'valor_arroba': '240',
    })
    client.post('/cadastro', data={
        'brinco': 'FILT-A01', 'sexo': 'M', 'raca': 'Angus',
        'data_compra': '2024-03-01', 'peso_compra': '300', 'valor_arroba': '240',
    }, follow_redirects=True)  # consome a flash de sucesso antes de checar o painel

    response = client.get('/painel?raca=Nelore')
    assert response.status_code == 200
    text = response.data.decode('utf-8')
    assert 'FILT-N01' in text
    assert 'FILT-A01' not in text


def test_painel_filtro_sexo(client):
    """Filtro por sexo retorna somente animais do sexo solicitado."""
    login(client)
    client.post('/cadastro', data={
        'brinco': 'FILT-SM01', 'sexo': 'M',
        'data_compra': '2024-03-01', 'peso_compra': '300', 'valor_arroba': '240',
    })
    client.post('/cadastro', data={
        'brinco': 'FILT-SF01', 'sexo': 'F',
        'data_compra': '2024-03-01', 'peso_compra': '300', 'valor_arroba': '240',
    }, follow_redirects=True)

    response = client.get('/painel?sexo=F')
    assert response.status_code == 200
    text = response.data.decode('utf-8')
    assert 'FILT-SF01' in text
    assert 'FILT-SM01' not in text


def test_export_csv_inclui_raca(client):
    """CSV exportado inclui coluna Raça quando animal tem raça definida."""
    login(client)
    client.post('/cadastro', data={
        'brinco': 'CSV-R01', 'sexo': 'M', 'raca': 'Senepol',
        'data_compra': '2024-03-01', 'peso_compra': '320', 'valor_arroba': '240',
    })
    response = client.get('/api/v1/export/animais.csv')
    assert response.status_code == 200
    text = response.data.decode('utf-8-sig')
    assert 'Raça' in text or 'Raca' in text


# ── Vacinação em lote (/vacinacao-coletiva) ─────────────────────────────────

def _make_user(username):
    from werkzeug.security import generate_password_hash
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
        (username, generate_password_hash("x")),
    )
    uid = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return uid


def test_vacinacao_coletiva_get_carrega(client):
    """GET /vacinacao-coletiva carrega a página com a lista de animais ativos."""
    login(client)
    response = client.get('/vacinacao-coletiva')
    assert response.status_code == 200


def test_vacinacao_coletiva_post_vacina_varios_animais(client):
    """POST com múltiplos animais registra medicação para cada um."""
    login(client)
    for brinco in ('VAC-LOTE-01', 'VAC-LOTE-02'):
        client.post('/cadastro', data={
            'brinco': brinco, 'sexo': 'M', 'data_compra': '2024-01-01',
            'peso_compra': '300', 'valor_arroba': '250',
        })
    rows = [_fetch_one("SELECT id FROM animais WHERE brinco=%s", (b,))
            for b in ('VAC-LOTE-01', 'VAC-LOTE-02')]
    ids = [str(r[0]) for r in rows]

    response = client.post('/vacinacao-coletiva', data={
        'animais_ids': ids,
        'data_aplicacao': '2024-06-01',
        'nome': 'Vacina Aftosa',
        'custo': '15.00',
        'obs': '',
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'vacinado' in response.data
    for r in rows:
        count = _fetch_one("SELECT COUNT(*) FROM medicacoes WHERE animal_id=%s AND nome_medicamento='Vacina Aftosa'", (r[0],))
        assert count[0] == 1


def test_vacinacao_coletiva_post_sem_animais_retorna_erro(client):
    """POST sem nenhum animal selecionado retorna 400 e não grava medicação."""
    login(client)
    response = client.post('/vacinacao-coletiva', data={
        'data_aplicacao': '2024-06-01',
        'nome': 'Vacina Sem Animal',
        'custo': '10.00',
        'obs': '',
    })
    assert response.status_code == 400
    count = _fetch_one("SELECT COUNT(*) FROM medicacoes WHERE nome_medicamento='Vacina Sem Animal'")
    assert count[0] == 0


def test_vacinacao_coletiva_ignora_animal_de_outro_usuario(client):
    """Animal_id de outro usuário incluído no POST não recebe a medicação (multi-tenant)."""
    login(client)
    outro_id = _make_user('vac_outro_user')
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id) "
        "VALUES ('VAC-ALHEIO-01','M','2024-01-01',1000,%s)", (outro_id,)
    )
    alheio_id = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()

    response = client.post('/vacinacao-coletiva', data={
        'animais_ids': [str(alheio_id)],
        'data_aplicacao': '2024-06-01',
        'nome': 'Vacina Invasora',
        'custo': '10.00',
        'obs': '',
    }, follow_redirects=True)

    assert response.status_code == 200
    count = _fetch_one("SELECT COUNT(*) FROM medicacoes WHERE animal_id=%s", (alheio_id,))
    assert count[0] == 0
