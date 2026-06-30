"""
Sprint 4 — Venda Coletiva.
Repositório: animal_repository.registrar_venda_lote / get_animais_ativos_com_ultimo_peso
Rota: /venda-lote
"""
import pytest
import itertools
from werkzeug.security import generate_password_hash
import db_config as dbc
from repositories import animal_repository

_seq = itertools.count(8000)


def _n():
    return next(_seq)


def _make_user():
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
        (f"vl_{_n()}", generate_password_hash("x")),
    )
    uid = cur.lastrowid
    conn.commit(); cur.close(); conn.close()
    return uid


def _make_animal(user_id, brinco=None, peso=None, data_pesagem='2024-01-01'):
    brinco = brinco or f"VL{_n()}"
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id)"
        " VALUES (%s, 'M', '2024-01-01', 1000, %s)",
        (brinco, user_id),
    )
    aid = cur.lastrowid
    if peso is not None:
        cur.execute(
            "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)",
            (aid, data_pesagem, peso),
        )
    conn.commit(); cur.close(); conn.close()
    return aid


def _purge(user_id):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    for sql in [
        "DELETE p FROM pesagens p JOIN animais a ON p.animal_id = a.id WHERE a.user_id = %s",
        "DELETE FROM animais WHERE user_id = %s",
        "DELETE FROM usuarios WHERE id = %s",
    ]:
        cur.execute(sql, (user_id,))
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit(); cur.close(); conn.close()


def _login(client, uid):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT username FROM usuarios WHERE id = %s", (uid,))
    username = cur.fetchone()[0]
    cur.close(); conn.close()
    client.post("/login", data={"username": username, "password": "x"}, follow_redirects=True)


@pytest.fixture
def um(app):
    uid = _make_user()
    yield uid
    _purge(uid)


# ── repositório ──────────────────────────────────────────────────────────────

def test_registrar_venda_lote_atualiza_animais_e_insere_pesagens(um):
    a1 = _make_animal(um, peso=400)
    a2 = _make_animal(um, peso=420)

    vendidos, invalidos = animal_repository.registrar_venda_lote(
        [(a1, 450.0, 4200.0), (a2, 460.0, 4300.0)], um, '2024-06-01'
    )

    assert vendidos == 2
    assert invalidos == []

    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT data_venda, preco_venda FROM animais WHERE id = %s", (a1,))
    data_venda, preco_venda = cur.fetchone()
    assert str(data_venda) == '2024-06-01'
    assert float(preco_venda) == 4200.0

    cur.execute(
        "SELECT peso FROM pesagens WHERE animal_id = %s AND data_pesagem = '2024-06-01'", (a1,)
    )
    assert float(cur.fetchone()[0]) == 450.0
    cur.close(); conn.close()


def test_registrar_venda_lote_ignora_animal_de_outro_usuario(um):
    outro_uid = _make_user()
    animal_outro = _make_animal(outro_uid, peso=300)

    try:
        vendidos, invalidos = animal_repository.registrar_venda_lote(
            [(animal_outro, 350.0, 3000.0)], um, '2024-06-01'
        )
        assert vendidos == 0
        assert invalidos == [animal_outro]
    finally:
        _purge(outro_uid)


def test_registrar_venda_lote_ignora_animal_ja_vendido(um):
    a1 = _make_animal(um, peso=400)
    animal_repository.registrar_venda_lote([(a1, 450.0, 4200.0)], um, '2024-06-01')

    # Segunda tentativa de venda do mesmo animal deve ser ignorada
    vendidos, invalidos = animal_repository.registrar_venda_lote(
        [(a1, 460.0, 4300.0)], um, '2024-07-01'
    )
    assert vendidos == 0
    assert invalidos == [a1]


def test_get_animais_ativos_com_ultimo_peso(um):
    a1 = _make_animal(um, peso=400, data_pesagem='2024-01-01')
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, '2024-03-01', 480)", (a1,)
    )
    conn.commit(); cur.close(); conn.close()
    a2 = _make_animal(um)  # sem nenhuma pesagem

    animais = animal_repository.get_animais_ativos_com_ultimo_peso(um)
    por_id = {row[0]: row for row in animais}

    assert float(por_id[a1][3]) == 480.0  # pega o peso mais recente, não o primeiro
    assert por_id[a2][3] is None


# ── rota ─────────────────────────────────────────────────────────────────────

def test_rota_venda_lote_requer_login(app):
    with app.test_client() as client:
        r = client.get("/venda-lote")
        assert r.status_code in (302, 401)


def test_rota_venda_lote_post_sucesso(app):
    uid = _make_user()
    a1 = _make_animal(uid, peso=400)
    a2 = _make_animal(uid, peso=420)
    try:
        with app.test_client() as client:
            _login(client, uid)
            r = client.post("/venda-lote", data={
                'data_venda': '2024-06-01',
                'valor_arroba': '300',
                'animal_ids[]': [str(a1), str(a2)],
                'pesos_venda[]': ['450', '460'],
            }, follow_redirects=True)
            assert r.status_code == 200
            assert b"2 animal" in r.data
    finally:
        _purge(uid)


def test_rota_venda_lote_post_sem_animais_retorna_400(app):
    uid = _make_user()
    try:
        with app.test_client() as client:
            _login(client, uid)
            r = client.post("/venda-lote", data={
                'data_venda': '2024-06-01',
                'valor_arroba': '300',
            })
            assert r.status_code == 400
    finally:
        _purge(uid)


def test_rota_venda_lote_calcula_preco_por_arroba(app):
    """peso=450, arroba=320 -> (450/30)*320 = 4800.00"""
    uid = _make_user()
    a1 = _make_animal(uid, peso=400)
    try:
        with app.test_client() as client:
            _login(client, uid)
            client.post("/venda-lote", data={
                'data_venda': '2024-06-01',
                'valor_arroba': '320',
                'animal_ids[]': [str(a1)],
                'pesos_venda[]': ['450'],
            })
        conn = dbc.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT preco_venda FROM animais WHERE id = %s", (a1,))
        preco = float(cur.fetchone()[0])
        cur.close(); conn.close()
        assert preco == 4800.0
    finally:
        _purge(uid)
