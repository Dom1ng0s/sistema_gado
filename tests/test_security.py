"""
Testes automatizados para os findings do audit de segurança.
Cobre: S4, S7, S8, B3.

Encolheu quando o HTML saiu: o que cobria formulário, rate limit de login,
405 em rota de exclusão e importação de CSV foi embora com as rotas. Ficou o
que não depende de tela — cabeçalhos, CSP, flags de cookie, escape nos emails
e o repositório.
"""
import itertools

from werkzeug.security import generate_password_hash

from conftest import login_as
from tests.dbcompat import connect


_seq = itertools.count(8500)


def _n():
    return next(_seq)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_user(sexo_animal='M'):
    """Cria usuário isolado com um animal. Retorna (user_id, username, animal_id)."""
    n = _n()
    username = f"sec_{n}"
    conn = connect()
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
    conn = connect()
    cur = conn.cursor()
    cur.execute("SET session_replication_role = 'replica'")
    for sql in [
        "DELETE FROM pesagens p USING animais a WHERE p.animal_id = a.id AND a.user_id = %s",
        "DELETE FROM medicacoes m USING animais a WHERE m.animal_id = a.id AND a.user_id = %s",
        "DELETE FROM reproducao WHERE user_id = %s",
        "DELETE FROM animais WHERE user_id=%s",
        "DELETE FROM usuarios WHERE id=%s",
    ]:
        cur.execute(sql, (user_id,))
    cur.execute("SET session_replication_role = 'origin'")
    conn.commit()
    cur.close()
    conn.close()


def _fetch_one(sql, params=()):
    conn = connect()
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


# ── Grupo A — S8: Security Headers ───────────────────────────────────────────

def test_security_headers_em_rota_autenticada(client):
    uid = _fetch_one("SELECT id FROM usuarios WHERE username='testuser'")[0]
    login_as(client, uid)
    r = client.get('/api/graficos/sexo')
    assert r.headers.get('X-Content-Type-Options') == 'nosniff'
    assert r.headers.get('X-Frame-Options') == 'DENY'
    assert r.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'


def test_security_headers_em_rota_publica(client):
    r = client.get('/proxy-cidades')
    assert r.headers.get('X-Content-Type-Options') == 'nosniff'
    assert r.headers.get('X-Frame-Options') == 'DENY'


def test_csp_de_api_nao_libera_nada(client):
    """Issue #46 — CSP como defesa em profundidade.

    Nenhuma resposta é documento, então a CSP certa é a que não libera fonte
    nenhuma: se um dia voltar a sair HTML daqui, ele nasce quebrado em vez de
    nascer permissivo.
    """
    r = client.get('/proxy-cidades')
    csp = r.headers.get('Content-Security-Policy')
    assert csp is not None
    assert "default-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "'unsafe-inline'" not in csp
    assert "cdn.jsdelivr.net" not in csp
    assert "fonts.googleapis.com" not in csp
    assert "fonts.gstatic.com" not in csp


def test_session_cookie_flags_configurados(app):
    """Issue #46 — HttpOnly + SameSite=Lax na config da sessão."""
    assert app.config['SESSION_COOKIE_HTTPONLY'] is True
    assert app.config['SESSION_COOKIE_SAMESITE'] == 'Lax'


# ── Grupo D — S4: proxy-cidades é público (dado não sensível) ────────────────

def test_proxy_cidades_sem_login_funciona(client):
    r = client.get('/proxy-cidades')
    # Pode retornar 200 (com dados) ou 500 (sem rede no CI) — nunca 302/401.
    assert r.status_code != 302
    assert r.status_code != 401


def test_proxy_cidades_com_login_funciona(client):
    uid = _fetch_one("SELECT id FROM usuarios WHERE username='testuser'")[0]
    login_as(client, uid)
    r = client.get('/proxy-cidades')
    assert r.status_code != 302
    assert r.status_code != 401


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


# ── Grupo E — B3: get_pesos_atuais sem duplicatas ────────────────────────────

def test_pesos_atuais_sem_duplicatas_com_duas_pesagens_mesmo_dia(app):
    """Duas pesagens no mesmo dia para o mesmo animal resultam em 1 linha."""
    from repositories import animal_repository

    uid, username, aid = _make_user()
    try:
        conn = connect()
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
