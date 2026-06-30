"""
Testes automatizados para os findings do audit de segurança.
Cobre: S1, S2, S3, S4, S5, S6, S7, S8, S9, B3, F1, F2, F3.
"""
import io
import itertools
import smtplib

import mysql.connector
import pytest
from werkzeug.security import generate_password_hash

import db_config as dbc
from extensions import limiter

DB_CONFIG = {
    "host": "localhost", "user": "gado_test",
    "password": "gado123", "port": 3306, "database": "sistema_gado_test",
}

_seq = itertools.count(8500)


def _n():
    return next(_seq)


# ── Helpers ──────────────────────────────────────────────────────────────────

def login(client):
    return client.post(
        '/login',
        data={'username': 'testuser', 'password': '123'},
        follow_redirects=True,
    )


def _make_user(sexo_animal='M'):
    """Cria usuário isolado com um animal. Retorna (user_id, username, animal_id)."""
    n = _n()
    username = f"sec_{n}"
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
        (username, generate_password_hash("x")),
    )
    uid = cur.lastrowid
    cur.execute(
        "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id) "
        "VALUES (%s, %s, '2024-01-01', 1000, %s)",
        (f"SEC-{n}", sexo_animal, uid),
    )
    aid = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return uid, username, aid


def _purge(user_id):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    for sql in [
        "DELETE p FROM pesagens p JOIN animais a ON p.animal_id=a.id WHERE a.user_id=%s",
        "DELETE m FROM medicacoes m JOIN animais a ON m.animal_id=a.id WHERE a.user_id=%s",
        "DELETE r FROM reproducao r WHERE user_id=%s",
        "DELETE FROM animais WHERE user_id=%s",
        "DELETE FROM usuarios WHERE id=%s",
    ]:
        cur.execute(sql, (user_id,))
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()
    cur.close()
    conn.close()


def _login_as(client, username):
    client.post('/login', data={'username': username, 'password': 'x'},
                follow_redirects=True)


def _fetch_one(sql, params=()):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


# ── Fixture rate-limit ────────────────────────────────────────────────────────

@pytest.fixture
def app_com_limite(app):
    """Habilita rate limiting apenas neste teste e limpa o storage antes e depois."""
    limiter.enabled = True
    limiter._storage.reset()
    yield app
    limiter._storage.reset()
    limiter.enabled = False


# ── Grupo A — S8: Security Headers ───────────────────────────────────────────

def test_security_headers_em_rota_autenticada(client):
    login(client)
    r = client.get('/painel')
    assert r.headers.get('X-Content-Type-Options') == 'nosniff'
    assert r.headers.get('X-Frame-Options') == 'SAMEORIGIN'
    assert r.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'


def test_security_headers_em_rota_publica(client):
    r = client.get('/login')
    assert r.headers.get('X-Content-Type-Options') == 'nosniff'
    assert r.headers.get('X-Frame-Options') == 'SAMEORIGIN'


# ── Grupo B — S1: Rate limit no login ────────────────────────────────────────

def test_login_retorna_429_apos_10_tentativas(app_com_limite, client):
    for _ in range(10):
        client.post('/login', data={'username': 'nobody', 'password': 'wrong'})
    r = client.post('/login', data={'username': 'nobody', 'password': 'wrong'})
    assert r.status_code == 429


# ── Grupo B — S5: Rate limit no verificar_codigo ─────────────────────────────

def test_verificar_codigo_retorna_429_apos_10_tentativas(app_com_limite, client):
    with client.session_transaction() as sess:
        sess['reset_email'] = 'teste@exemplo.com'
        sess['reset_expires_at'] = 9_999_999_999.0
    for _ in range(10):
        client.post('/verificar_codigo', data={'codigo': '000000'})
    r = client.post('/verificar_codigo', data={'codigo': '000000'})
    assert r.status_code == 429


# ── Grupo C — S2: Mutating GET → POST ────────────────────────────────────────

def test_excluir_animal_get_retorna_405(client):
    login(client)
    r = client.get('/excluir_animal/1')
    assert r.status_code == 405


def test_excluir_pesagem_get_retorna_405(client):
    login(client)
    r = client.get('/excluir_pesagem/1')
    assert r.status_code == 405


def test_restaurar_animal_get_retorna_405(client):
    login(client)
    r = client.get('/restaurar_animal/1')
    assert r.status_code == 405


def test_baixar_agendamento_get_retorna_405(client):
    login(client)
    r = client.get('/financeiro/baixar/1')
    assert r.status_code == 405


def test_excluir_animal_post_funciona(client):
    """POST no excluir_animal com animal válido executa soft-delete e redireciona."""
    login(client)
    # Cria animal via rota
    client.post('/cadastro', data={
        'brinco': 'DEL-SEC-01', 'sexo': 'M',
        'data_compra': '2024-01-01', 'peso_compra': '300', 'valor_arroba': '280',
    })
    row = _fetch_one(
        "SELECT id FROM animais WHERE brinco='DEL-SEC-01' AND deleted_at IS NULL"
    )
    assert row is not None
    aid = row[0]

    r = client.post(f'/excluir_animal/{aid}')
    assert r.status_code in (302, 200)

    row2 = _fetch_one("SELECT deleted_at FROM animais WHERE id=%s", (aid,))
    assert row2[0] is not None  # deve ter deleted_at setado


def test_restaurar_animal_post_funciona(client):
    """POST no restaurar_animal restaura um animal soft-deleted."""
    login(client)
    client.post('/cadastro', data={
        'brinco': 'RST-SEC-01', 'sexo': 'M',
        'data_compra': '2024-01-01', 'peso_compra': '300', 'valor_arroba': '280',
    })
    row = _fetch_one(
        "SELECT id FROM animais WHERE brinco='RST-SEC-01' AND deleted_at IS NULL"
    )
    assert row is not None
    aid = row[0]

    # Soft-delete direto
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE animais SET deleted_at=NOW() WHERE id=%s", (aid,))
    conn.commit(); cur.close(); conn.close()

    r = client.post(f'/restaurar_animal/{aid}')
    assert r.status_code in (302, 200)

    row2 = _fetch_one("SELECT deleted_at FROM animais WHERE id=%s", (aid,))
    assert row2[0] is None  # deve ter sido restaurado


# ── Grupo C — F1: baixar_agendamento feedback ─────────────────────────────────

def test_baixar_agendamento_inexistente_exibe_mensagem_erro(client):
    login(client)
    r = client.post('/financeiro/baixar/99999', follow_redirects=True)
    assert r.status_code == 200
    assert ('não encontrado'.encode('utf-8') in r.data
            or 'erro'.encode('utf-8') in r.data
            or b'erro' in r.data.lower())


def test_baixar_agendamento_valido_exibe_mensagem_sucesso(client):
    login(client)
    uid = _fetch_one("SELECT id FROM usuarios WHERE username='testuser'")[0]

    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO financial_schedule (user_id, descricao, valor, vencimento, status) "
        "VALUES (%s, 'Conta teste baixa', 100.0, '2024-12-01', 'pendente')",
        (uid,)
    )
    agend_id = cur.lastrowid
    conn.commit(); cur.close(); conn.close()

    r = client.post(f'/financeiro/baixar/{agend_id}', follow_redirects=True)
    assert r.status_code == 200
    assert ('sucesso'.encode('utf-8') in r.data or b'sucesso' in r.data.lower()
            or 'baixada'.encode('utf-8') in r.data)

    row = _fetch_one("SELECT status FROM financial_schedule WHERE id=%s", (agend_id,))
    assert row[0] == 'pago'


# ── Grupo D — S4: proxy-cidades requer login ─────────────────────────────────

def test_proxy_cidades_sem_login_redireciona(client):
    r = client.get('/proxy-cidades')
    assert r.status_code in (301, 302)


def test_proxy_cidades_com_login_funciona(client):
    login(client)
    r = client.get('/proxy-cidades')
    # Pode retornar 200 (com dados) ou 500 (sem rede no CI) — nunca 302/401
    assert r.status_code != 302
    assert r.status_code != 401


# ── Grupo D — S3: PDF IDOR ───────────────────────────────────────────────────

def test_pdf_status_sem_job_na_sessao_retorna_404(client):
    login(client)
    fake_uuid = 'a1b2c3d4-e5f6-4a7b-8c9d-e0f1a2b3c4d5'
    r = client.get(f'/api/v1/relatorio/pdf/{fake_uuid}/status')
    assert r.status_code == 404


def test_pdf_download_sem_job_na_sessao_retorna_404(client):
    login(client)
    fake_uuid = 'a1b2c3d4-e5f6-4a7b-8c9d-e0f1a2b3c4d5'
    r = client.get(f'/api/v1/relatorio/pdf/{fake_uuid}/download')
    assert r.status_code == 404


def test_pdf_status_uuid_invalido_retorna_404(client):
    login(client)
    r = client.get('/api/v1/relatorio/pdf/nao-e-um-uuid/status')
    assert r.status_code == 404


# ── Grupo D — F3: touro_id ownership ────────────────────────────────────────

def test_reproducao_touro_outro_usuario_rejeitado(app, client):
    uid_a, user_a, touro_id = _make_user(sexo_animal='M')   # touro de A
    uid_b, user_b, vaca_id  = _make_user(sexo_animal='F')   # vaca de B

    try:
        _login_as(client, user_b)
        antes = _fetch_one(
            "SELECT COUNT(*) FROM reproducao WHERE user_id=%s", (uid_b,)
        )[0]

        client.post('/reproducao', data={
            'vaca_id': str(vaca_id),
            'touro_id': str(touro_id),   # touro pertence ao user A
            'data_cobertura': '2024-05-01',
            'resultado': 'aborto',
        })

        depois = _fetch_one(
            "SELECT COUNT(*) FROM reproducao WHERE user_id=%s", (uid_b,)
        )[0]
        assert depois == antes  # nenhuma reprodução deve ter sido inserida
    finally:
        _purge(uid_a)
        _purge(uid_b)


# ── Grupo F — S6: exceções não vazam para o usuário ─────────────────────────

def test_erro_importacao_csv_nao_vaza_detalhes_excecao(client):
    """Uma exceção interna não expõe mensagem com detalhes de schema."""
    login(client)
    # Envia CSV malformado para disparar erro interno
    dados = b"brinco,sexo,data_compra,peso_kg,valor_arroba\n" + b"\x00" * 100
    r = client.post(
        '/importar-csv',
        data={'arquivo': (io.BytesIO(dados), 'test.csv')},
        content_type='multipart/form-data',
        follow_redirects=True,
    )
    assert r.status_code == 200
    # A mensagem de erro não deve conter nomes de colunas SQL ou tracebacks
    assert b'Table' not in r.data
    assert b'Column' not in r.data
    assert b'Traceback' not in r.data


# ── Grupo F — S7: HTML-escape em emails ─────────────────────────────────────

def test_send_feedback_request_escapa_html_no_username(monkeypatch):
    """Username com HTML malicioso é escapado antes de entrar no corpo do email."""
    from utils import email_service

    capturados = []

    def _mock_send(to_email, subject, html):
        capturados.append(html)

    monkeypatch.setattr(email_service, '_send', _mock_send)
    email_service.send_feedback_request(
        'vitima@example.com',
        '<script>alert("xss")</script>',
    )

    assert len(capturados) == 1
    html = capturados[0]
    assert '<script>' not in html
    assert '&lt;script&gt;' in html


def test_send_welcome_email_escapa_html_no_username(monkeypatch):
    """send_welcome_email: username com HTML é escapado (verifica HTML antes do encode MIME)."""
    import smtplib as _smtplib
    import base64
    import re

    sent_msgs = []

    class MockSMTP:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def ehlo(self): pass
        def starttls(self, **kw): pass
        def login(self, *a): pass
        def sendmail(self, frm, to, msg): sent_msgs.append(msg)

    monkeypatch.setattr(_smtplib, 'SMTP', MockSMTP)
    monkeypatch.setenv('MAIL_USERNAME', 'sender@test.com')
    monkeypatch.setenv('MAIL_PASSWORD', 'secret')

    from utils.email_service import send_welcome_email
    send_welcome_email('to@example.com', '<img src=x onerror=alert(1)>')

    assert len(sent_msgs) == 1
    raw = sent_msgs[0]

    # MIME bodies are base64-encoded; decode to inspect the actual HTML content
    match = re.search(
        r'Content-Transfer-Encoding: base64\s*\n\n(.+?)(?=\n--|\Z)',
        raw, re.DOTALL
    )
    if match:
        b64 = match.group(1).replace('\n', '').replace('\r', '')
        decoded = base64.b64decode(b64 + '==').decode('utf-8', errors='replace')
        assert '<img src=x' not in decoded, "Username não escapado: raw <img> encontrado no HTML"
        assert '&lt;img' in decoded, "Esperava '&lt;img' escapado no HTML"
    else:
        # Se não tiver base64, verifica diretamente no raw
        assert '<img src=x' not in raw


# ── Grupo G — F2: CSV race condition / duplicate key ─────────────────────────

def test_csv_import_brinco_ja_existente_reporta_erro_nao_duplica(client):
    """Brinco duplicado no CSV gera linha de erro e não insere segundo registro."""
    login(client)
    uid = _fetch_one("SELECT id FROM usuarios WHERE username='testuser'")[0]

    # Garante que o brinco existe no banco
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT IGNORE INTO animais (brinco, sexo, data_compra, preco_compra, user_id) "
        "VALUES ('CSV-DUP-001','M','2024-01-01',500,%s)",
        (uid,),
    )
    conn.commit(); cur.close(); conn.close()

    csv_content = (
        "brinco,sexo,data_compra,peso_kg,valor_arroba\r\n"
        "CSV-DUP-001,M,2024-06-01,300,280\r\n"
    ).encode('utf-8')

    r = client.post(
        '/importar-csv',
        data={'arquivo': (io.BytesIO(csv_content), 'import.csv')},
        content_type='multipart/form-data',
        follow_redirects=True,
    )
    assert r.status_code == 200

    count = _fetch_one(
        "SELECT COUNT(*) FROM animais WHERE brinco='CSV-DUP-001' AND user_id=%s",
        (uid,),
    )[0]
    assert count == 1  # não deve ter inserido duplicata

    # A resposta deve indicar 0 inseridos e ao menos 1 erro
    assert b'0' in r.data or 'erro'.encode('utf-8') in r.data.lower()


# ── Grupo E — B3: get_pesos_atuais sem duplicatas ────────────────────────────

def test_pesos_atuais_sem_duplicatas_com_duas_pesagens_mesmo_dia(app):
    """Duas pesagens no mesmo dia para o mesmo animal resultam em 1 linha."""
    from repositories import animal_repository

    uid, username, aid = _make_user()
    try:
        conn = dbc.get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s,'2024-06-01',300)",
            (aid,),
        )
        cur.execute(
            "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s,'2024-06-01',310)",
            (aid,),
        )
        conn.commit(); cur.close(); conn.close()

        pesos = animal_repository.get_pesos_atuais_rebanho(uid)
        assert len(pesos) == 1
        assert float(pesos[0][0]) in (300.0, 310.0)
    finally:
        _purge(uid)
