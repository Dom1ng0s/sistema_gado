import pytest

def login(client):
    return client.post('/login', data={'username': 'testuser', 'password': '123'}, follow_redirects=True)

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
    
    # Validação matemática simples:
    assert b"1,500.00" in response.data # Total Mensal
    assert b"5.00" in response.data     # Diária