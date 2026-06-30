"""
Sprint 7 — Painel de Transações unificado.
Rota: /transacoes — hub que agrupa as operações de entrada e saída de animais.
"""
import pytest
import itertools
from werkzeug.security import generate_password_hash
import db_config as dbc

_seq = itertools.count(11000)


def _n():
    return next(_seq)


def _make_user():
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
        (f"tr_{_n()}", generate_password_hash("x")),
    )
    uid = cur.lastrowid
    conn.commit(); cur.close(); conn.close()
    return uid


def _purge(user_id):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM usuarios WHERE id = %s", (user_id,))
    conn.commit(); cur.close(); conn.close()


def _login(client, uid):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT username FROM usuarios WHERE id = %s", (uid,))
    username = cur.fetchone()[0]
    cur.close(); conn.close()
    client.post("/login", data={"username": username, "password": "x"}, follow_redirects=True)


def test_rota_transacoes_requer_login(app):
    with app.test_client() as client:
        r = client.get("/transacoes")
        assert r.status_code in (302, 401)


def test_rota_transacoes_lista_todos_os_cards(app):
    uid = _make_user()
    try:
        with app.test_client() as client:
            _login(client, uid)
            r = client.get("/transacoes")
            assert r.status_code == 200
            assert b"Animal Individual" in r.data
            assert b"Lote de Animais" in r.data
            assert b"Importar CSV" in r.data
            assert b"Venda Coletiva" in r.data
            assert b"Venda Individual" in r.data
    finally:
        _purge(uid)


def test_rota_transacoes_links_resolvem(app):
    uid = _make_user()
    try:
        with app.test_client() as client:
            _login(client, uid)
            for rota in ['/cadastro', '/cadastro-lote', '/importar-csv', '/venda-lote']:
                r = client.get(rota)
                assert r.status_code == 200, f"{rota} retornou {r.status_code}"
    finally:
        _purge(uid)


def test_painel_nao_contem_mais_novo_animal_novo_lote(app):
    uid = _make_user()
    try:
        with app.test_client() as client:
            _login(client, uid)
            r = client.get("/painel")
            assert b"+ Novo Animal" not in r.data
            assert b"+ Lote</a>" not in r.data
            assert b"Transa\xc3\xa7\xc3\xb5es" in r.data or b"Transacoes" in r.data
    finally:
        _purge(uid)
