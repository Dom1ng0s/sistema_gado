import pytest

# Helper para logar antes de cada teste
def login(client):
    return client.post('/login', data={'username': 'testuser', 'password': '123'}, follow_redirects=True)

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
    assert b"ATIVO" in response_painel.data

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
    
    # 2. Vende o animal (ID 3, pois é o terceiro animal criado na sessão de teste)
    # TEST-01 (ID 1), DUPLICADO (ID 2), VENDIDO-01 (ID 3)
    response = client.post('/vender/3', data={ 
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