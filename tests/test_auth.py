import itertools
import pytest
from flask import session
from werkzeug.security import generate_password_hash

import db_config as dbc

_seq = itertools.count(11000)


def _n():
    return next(_seq)


def _fetch_one(sql, params=()):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def _make_user_with_email(email):
    """Cria usuário com email definido — necessário para fluxos de reset de senha."""
    n = _n()
    username = f"au_{n}"
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash, email) VALUES (%s, %s, %s)",
        (username, generate_password_hash("senhaAntiga1"), email),
    )
    uid = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return uid, username


def _purge_user(user_id):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    cur.execute("DELETE FROM password_reset_tokens WHERE user_id = %s", (user_id,))
    cur.execute("DELETE FROM configuracoes WHERE user_id = %s", (user_id,))
    cur.execute("DELETE FROM usuarios WHERE id = %s", (user_id,))
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()
    cur.close()
    conn.close()


@pytest.fixture
def mock_smtp(monkeypatch):
    """Substitui smtplib.SMTP para que nenhum email real seja enviado nos testes."""
    import smtplib as _smtplib

    sent = []

    class MockSMTP:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def ehlo(self): pass
        def starttls(self, **kw): pass
        def login(self, *a): pass
        def sendmail(self, frm, to, msg): sent.append((to, msg))

    monkeypatch.setattr(_smtplib, 'SMTP', MockSMTP)
    monkeypatch.setenv('MAIL_USERNAME', 'sender@test.com')
    monkeypatch.setenv('MAIL_PASSWORD', 'secret')
    return sent

def test_login_page_loads(client):
    """Verifica se a página de login carrega (GET)."""
    response = client.get('/login')
    assert response.status_code == 200
    assert b"Bem-vindo de volta" in response.data

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
    assert b"Bem-vindo de volta" in response.data
    assert b"Meu Rebanho" not in response.data


# ── /novo_usuario ────────────────────────────────────────────────────────────

def test_novo_usuario_get_carrega(client):
    response = client.get('/novo_usuario')
    assert response.status_code == 200


def test_novo_usuario_post_cria_conta(client, mock_smtp):
    username = f"novo_{_n()}"
    response = client.post('/novo_usuario', data={
        'username': username,
        'password': 'senha123',
        'email': f'{username}@example.com',
        'nome_fazenda': 'Fazenda Teste',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert response.request.path == '/login'

    row = _fetch_one("SELECT id, email FROM usuarios WHERE username=%s", (username,))
    assert row is not None
    assert row[1] == f'{username}@example.com'
    _purge_user(row[0])


def test_novo_usuario_username_duplicado_retorna_erro(client, mock_smtp):
    username = f"dup_{_n()}"
    client.post('/novo_usuario', data={
        'username': username, 'password': 'senha123', 'email': f'{username}@example.com',
    })
    row = _fetch_one("SELECT id FROM usuarios WHERE username=%s", (username,))

    response = client.post('/novo_usuario', data={
        'username': username, 'password': 'outrasenha', 'email': 'outro@example.com',
    })
    assert response.status_code == 400
    # Mensagem genérica (issue #50): não revela QUAL campo colidiu.
    assert 'Não foi possível criar a conta'.encode('utf-8') in response.data
    assert b'j\xc3\xa1 existe' not in response.data
    _purge_user(row[0])


def test_novo_usuario_email_duplicado_retorna_erro(client, mock_smtp):
    username1 = f"emaildup1_{_n()}"
    username2 = f"emaildup2_{_n()}"
    email = f"{username1}@example.com"
    client.post('/novo_usuario', data={
        'username': username1, 'password': 'senha123', 'email': email,
    })
    row = _fetch_one("SELECT id FROM usuarios WHERE username=%s", (username1,))

    response = client.post('/novo_usuario', data={
        'username': username2, 'password': 'senha123', 'email': email,
    })
    assert response.status_code == 400
    # Mensagem genérica (issue #50): não revela QUAL campo colidiu.
    assert 'Não foi possível criar a conta'.encode('utf-8') in response.data
    assert 'já está cadastrado'.encode('utf-8') not in response.data
    _purge_user(row[0])


def test_novo_usuario_sem_email_retorna_erro(client):
    response = client.post('/novo_usuario', data={
        'username': f"sememail_{_n()}", 'password': 'senha123',
    })
    assert response.status_code == 400
    assert 'obrigatório'.encode('utf-8') in response.data


# ── Recuperação de senha ─────────────────────────────────────────────────────

def test_esqueci_senha_email_existente_redireciona_para_verificar_codigo(client, mock_smtp):
    uid, _ = _make_user_with_email(f"reset_{_n()}@example.com")
    row = _fetch_one("SELECT email FROM usuarios WHERE id=%s", (uid,))

    response = client.post('/esqueci_senha', data={'email': row[0]}, follow_redirects=True)
    assert response.status_code == 200
    assert response.request.path == '/verificar_codigo'
    _purge_user(uid)


def test_esqueci_senha_email_inexistente_nao_vaza_informacao(client, mock_smtp):
    """Email que não existe não deve gerar token nem travar em verificar_codigo (sem sessão)."""
    response = client.post('/esqueci_senha', data={'email': 'ninguem_aqui@example.com'},
                            follow_redirects=True)
    assert response.status_code == 200
    # Sem sessão de reset válida, verificar_codigo redireciona de volta
    assert response.request.path == '/esqueci_senha'


def test_fluxo_completo_reset_de_senha(client, mock_smtp):
    """esqueci_senha -> verificar_codigo -> nova_senha -> login com a nova senha."""
    email = f"fluxo_{_n()}@example.com"
    uid, username = _make_user_with_email(email)

    client.post('/esqueci_senha', data={'email': email}, follow_redirects=True)
    token_row = _fetch_one(
        "SELECT code FROM password_reset_tokens WHERE user_id=%s AND used=0", (uid,)
    )
    assert token_row is not None
    codigo = token_row[0]

    r = client.post('/verificar_codigo', data={'codigo': codigo}, follow_redirects=True)
    assert r.status_code == 200
    assert r.request.path == '/nova_senha'

    r2 = client.post('/nova_senha', data={
        'password': 'novaSenha123', 'password_confirm': 'novaSenha123',
    }, follow_redirects=True)
    assert r2.status_code == 200
    assert r2.request.path == '/login'

    r3 = client.post('/login', data={'username': username, 'password': 'novaSenha123'},
                      follow_redirects=True)
    assert b"Meu Rebanho" in r3.data
    _purge_user(uid)


def test_verificar_codigo_invalido_mostra_erro(client, mock_smtp):
    email = f"codigoerrado_{_n()}@example.com"
    uid, _ = _make_user_with_email(email)
    client.post('/esqueci_senha', data={'email': email}, follow_redirects=True)

    r = client.post('/verificar_codigo', data={'codigo': '000000'}, follow_redirects=True)
    assert r.status_code == 200
    assert 'inválido'.encode('utf-8') in r.data or 'expirado'.encode('utf-8') in r.data
    _purge_user(uid)


def test_reenviar_codigo_gera_novo_token(client, mock_smtp):
    email = f"reenvio_{_n()}@example.com"
    uid, _ = _make_user_with_email(email)
    client.post('/esqueci_senha', data={'email': email}, follow_redirects=True)
    primeiro = _fetch_one(
        "SELECT code FROM password_reset_tokens WHERE user_id=%s AND used=0", (uid,)
    )[0]

    r = client.post('/reenviar-codigo', follow_redirects=True)
    assert r.status_code == 200
    segundo = _fetch_one(
        "SELECT code FROM password_reset_tokens WHERE user_id=%s AND used=0", (uid,)
    )[0]
    assert segundo != primeiro
    _purge_user(uid)


def test_nova_senha_confirmacao_diferente_retorna_erro(client, mock_smtp):
    email = f"mismatch_{_n()}@example.com"
    uid, username = _make_user_with_email(email)
    client.post('/esqueci_senha', data={'email': email}, follow_redirects=True)
    codigo = _fetch_one(
        "SELECT code FROM password_reset_tokens WHERE user_id=%s AND used=0", (uid,)
    )[0]
    client.post('/verificar_codigo', data={'codigo': codigo}, follow_redirects=True)

    r = client.post('/nova_senha', data={
        'password': 'senhaA123', 'password_confirm': 'senhaB456',
    })
    assert r.status_code == 200
    assert 'não coincidem'.encode('utf-8') in r.data

    # Login com a senha antiga ainda deve funcionar (nada foi alterado)
    r2 = client.post('/login', data={'username': username, 'password': 'senhaAntiga1'},
                      follow_redirects=True)
    assert b"Meu Rebanho" in r2.data
    _purge_user(uid)


# ── /conta/apagar ────────────────────────────────────────────────────────────

def test_apagar_conta_confirmacao_correta_exclui_usuario(client):
    uid, username = _make_user_with_email(f"apagar_{_n()}@example.com")
    client.post('/login', data={'username': username, 'password': 'senhaAntiga1'},
                follow_redirects=True)

    r = client.post('/conta/apagar', data={'confirmacao': username}, follow_redirects=True)
    assert r.status_code == 200

    row = _fetch_one("SELECT id FROM usuarios WHERE id=%s", (uid,))
    assert row is None


def test_apagar_conta_confirmacao_incorreta_mantem_usuario(client):
    uid, username = _make_user_with_email(f"manter_{_n()}@example.com")
    client.post('/login', data={'username': username, 'password': 'senhaAntiga1'},
                follow_redirects=True)

    r = client.post('/conta/apagar', data={'confirmacao': 'nome_errado'}, follow_redirects=True)
    assert r.status_code == 200

    row = _fetch_one("SELECT id FROM usuarios WHERE id=%s", (uid,))
    assert row is not None
    _purge_user(uid)