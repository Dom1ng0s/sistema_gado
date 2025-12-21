import pytest
from flask import session

def test_login_page_loads(client):
    """Verifica se a página de login carrega (GET)."""
    response = client.get('/login')
    assert response.status_code == 200
    assert b"Acesso ao Rebanho" in response.data

def test_login_sucesso(client):
    """Verifica login com credenciais corretas."""
    response = client.post('/login', data={
        'username': 'testuser',
        'password': '123'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Meu Rebanho" in response.data  # Texto presente na dashboard
    assert b"Sair" in response.data         # Botão de logout visível

def test_login_falha(client):
    """Verifica login com senha errada."""
    response = client.post('/login', data={
        'username': 'testuser',
        'password': 'errada'
    }, follow_redirects=True)
    
    assert b"incorretos" in response.data
    assert b"Meu Rebanho" not in response.data

def test_acesso_protegido(client):
    """Tenta acessar painel sem estar logado."""
    # Garante que estamos deslogados
    client.get('/logout')
    
    response = client.get('/painel', follow_redirects=True)
    # Deve redirecionar para login
    assert b"Acesso ao Rebanho" in response.data
    assert b"Meu Rebanho" not in response.data