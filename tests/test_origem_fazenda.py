"""
Sprint 5 — Filtro "Nascidos na Fazenda" no painel.
Repositório: animal_repository.get_animais_paginados / count_animais (parâmetro origem)
Rota: GET /painel?origem=fazenda
"""
import pytest
import itertools
from werkzeug.security import generate_password_hash
import db_config as dbc
from repositories import animal_repository

_seq = itertools.count(9000)


def _n():
    return next(_seq)


def _make_user():
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
        (f"of_{_n()}", generate_password_hash("x")),
    )
    uid = cur.lastrowid
    conn.commit(); cur.close(); conn.close()
    return uid


def _make_animal_comprado(user_id, brinco=None):
    brinco = brinco or f"COMP{_n()}"
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id)"
        " VALUES (%s, 'M', '2024-01-01', 1000, %s)",
        (brinco, user_id),
    )
    aid = cur.lastrowid
    conn.commit(); cur.close(); conn.close()
    return aid


def _make_animal_nascido_fazenda(user_id, brinco=None, vendido=False):
    brinco = brinco or f"NASC{_n()}"
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    if vendido:
        cur.execute(
            "INSERT INTO animais (brinco, sexo, data_nascimento, user_id, data_venda, preco_venda)"
            " VALUES (%s, 'F', '2024-02-01', %s, '2024-08-01', 1500)",
            (brinco, user_id),
        )
    else:
        cur.execute(
            "INSERT INTO animais (brinco, sexo, data_nascimento, user_id)"
            " VALUES (%s, 'F', '2024-02-01', %s)",
            (brinco, user_id),
        )
    aid = cur.lastrowid
    conn.commit(); cur.close(); conn.close()
    return aid


def _add_pesagem(animal_id, data, peso):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)",
        (animal_id, data, peso),
    )
    conn.commit(); cur.close(); conn.close()


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

def test_get_animais_paginados_origem_fazenda_filtra_corretamente(um):
    comprado = _make_animal_comprado(um)
    nascido = _make_animal_nascido_fazenda(um)

    animais = animal_repository.get_animais_paginados(um, 20, 0, origem='fazenda')
    ids = [a[0] for a in animais]

    assert nascido in ids
    assert comprado not in ids


def test_count_animais_origem_fazenda(um):
    _make_animal_comprado(um)
    _make_animal_nascido_fazenda(um)
    _make_animal_nascido_fazenda(um)

    total = animal_repository.count_animais(um, origem='fazenda')
    assert total == 2


def test_origem_fazenda_combinado_com_status_vendido(um):
    nascido_ativo = _make_animal_nascido_fazenda(um)
    nascido_vendido = _make_animal_nascido_fazenda(um, vendido=True)

    animais = animal_repository.get_animais_paginados(um, 20, 0, status='vendidos', origem='fazenda')
    ids = [a[0] for a in animais]

    assert ids == [nascido_vendido]
    assert nascido_ativo not in ids


def test_origem_sem_filtro_retorna_todos(um):
    comprado = _make_animal_comprado(um)
    nascido = _make_animal_nascido_fazenda(um)

    animais = animal_repository.get_animais_paginados(um, 20, 0)
    ids = {a[0] for a in animais}
    assert {comprado, nascido}.issubset(ids)


def test_get_gmd_medio_rebanho_origem_fazenda_filtra(um):
    comprado = _make_animal_comprado(um)
    nascido = _make_animal_nascido_fazenda(um)
    _add_pesagem(comprado, '2024-01-01', 200)
    _add_pesagem(comprado, '2024-01-11', 210)  # gmd 1.0
    _add_pesagem(nascido, '2024-02-01', 100)
    _add_pesagem(nascido, '2024-02-11', 105)   # gmd 0.5

    gmd_fazenda = animal_repository.get_gmd_medio_rebanho(um, origem='fazenda')
    gmd_geral = animal_repository.get_gmd_medio_rebanho(um)

    assert gmd_fazenda == pytest.approx(0.5)
    assert gmd_geral == pytest.approx(0.75)


# ── rota ─────────────────────────────────────────────────────────────────────

def test_rota_painel_origem_fazenda(app):
    uid = _make_user()
    comprado = _make_animal_comprado(uid, brinco='ROTACOMP')
    nascido = _make_animal_nascido_fazenda(uid, brinco='ROTANASC')
    try:
        with app.test_client() as client:
            _login(client, uid)
            r = client.get("/painel?origem=fazenda")
            assert r.status_code == 200
            assert b"ROTANASC" in r.data
            assert b"ROTACOMP" not in r.data
    finally:
        _purge(uid)
