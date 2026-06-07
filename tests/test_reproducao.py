"""
Testes da Entrega 2 — Hereditariedade Animal.
Repositórios: reproducao_repository, animal_repository (hereditariedade)
Blueprint: operacional (rotas /progenie, /reproducao, /ranking-touros)
"""
import pytest
import itertools
from werkzeug.security import generate_password_hash
import db_config as dbc
from repositories import animal_repository, reproducao_repository

_seq = itertools.count(7000)


def _n():
    return next(_seq)


# ── helpers de banco ──────────────────────────────────────────────────────────

def _make_user():
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
        (f"rp_{_n()}", generate_password_hash("x")),
    )
    uid = cur.lastrowid
    conn.commit(); cur.close(); conn.close()
    return uid


def _make_animal(user_id, sexo="M", brinco=None, pai_id=None, mae_id=None):
    brinco = brinco or f"RP{_n()}"
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id, pai_id, mae_id)"
        " VALUES (%s, %s, '2024-01-01', 1000, %s, %s, %s)",
        (brinco, sexo, user_id, pai_id, mae_id),
    )
    aid = cur.lastrowid
    cur.execute(
        "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, '2024-01-01', 300)",
        (aid,),
    )
    conn.commit(); cur.close(); conn.close()
    return aid


def _purge(user_id):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    for sql in [
        "DELETE oa FROM ocupacao_animais oa JOIN ocupacoes o ON oa.ocupacao_id = o.id JOIN modulos m ON o.modulo_id = m.id WHERE m.user_id = %s",
        "DELETE o FROM ocupacoes o JOIN modulos m ON o.modulo_id = m.id WHERE m.user_id = %s",
        "DELETE FROM modulos WHERE user_id = %s",
        "DELETE FROM pastos WHERE user_id = %s",
        "DELETE p FROM pesagens p JOIN animais a ON p.animal_id = a.id WHERE a.user_id = %s",
        "DELETE FROM reproducao WHERE user_id = %s",
        "DELETE FROM animais WHERE user_id = %s",
        "DELETE FROM estoque_movimentacoes WHERE user_id = %s",
        "DELETE FROM estoque_produtos WHERE user_id = %s",
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
    client.post("/login", data={"username": username, "password": "x"},
                follow_redirects=True)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def um(app):
    uid = _make_user()
    yield uid
    _purge(uid)


@pytest.fixture
def dois(app):
    uid_a, uid_b = _make_user(), _make_user()
    yield uid_a, uid_b
    _purge(uid_a)
    _purge(uid_b)


# ── CRUD reproducao_repository ────────────────────────────────────────────────

def test_insert_e_get_reproducao(um):
    vaca_id = _make_animal(um, sexo="F")
    touro_id = _make_animal(um, sexo="M")
    rid = reproducao_repository.insert_reproducao(
        um, vaca_id, touro_id, None, "2024-03-01", "2024-12-01", "vivo"
    )
    assert rid is not None
    eventos = reproducao_repository.get_reproducao_by_vaca(vaca_id, um)
    assert len(eventos) == 1
    assert eventos[0][3] == "vivo"


def test_insert_reproducao_touro_externo(um):
    vaca_id = _make_animal(um, sexo="F")
    rid = reproducao_repository.insert_reproducao(
        um, vaca_id, None, "Sêmen Importado", "2024-04-15", None, "aborto"
    )
    assert rid is not None
    eventos = reproducao_repository.get_reproducao_by_vaca(vaca_id, um)
    assert eventos[0][3] == "aborto"
    assert eventos[0][5] == "Sêmen Importado"


def test_multiplos_eventos_ordenados(um):
    vaca_id = _make_animal(um, sexo="F")
    reproducao_repository.insert_reproducao(um, vaca_id, None, "A", "2024-01-01", None, "aborto")
    reproducao_repository.insert_reproducao(um, vaca_id, None, "B", "2024-06-01", None, "vivo")
    reproducao_repository.insert_reproducao(um, vaca_id, None, "C", "2024-09-01", None, "natimorto")
    eventos = reproducao_repository.get_reproducao_by_vaca(vaca_id, um)
    assert len(eventos) == 3
    # Ordenados por data DESC (mais recente primeiro)
    assert str(eventos[0][1]) > str(eventos[1][1]) > str(eventos[2][1])


# ── Isolamento multi-tenant ───────────────────────────────────────────────────

def test_isolamento_reproducao_por_user(dois):
    uid_a, uid_b = dois
    vaca_a = _make_animal(uid_a, sexo="F")
    vaca_b = _make_animal(uid_b, sexo="F")
    reproducao_repository.insert_reproducao(uid_a, vaca_a, None, "X", "2024-05-01", None, "vivo")
    reproducao_repository.insert_reproducao(uid_b, vaca_b, None, "Y", "2024-05-01", None, "vivo")
    # uid_b não vê evento da vaca_a
    assert reproducao_repository.get_reproducao_by_vaca(vaca_a, uid_b) == []
    # uid_a não vê evento da vaca_b
    assert reproducao_repository.get_reproducao_by_vaca(vaca_b, uid_a) == []


# ── Progênie (animal_repository) ─────────────────────────────────────────────

def test_progenie_pai(um):
    touro_id = _make_animal(um, sexo="M")
    filho1 = _make_animal(um, sexo="F", pai_id=touro_id)
    filho2 = _make_animal(um, sexo="M", pai_id=touro_id)
    filhos = animal_repository.get_progenie_by_touro(touro_id, um)
    ids = [f[0] for f in filhos]
    assert filho1 in ids
    assert filho2 in ids
    papeis = {f[0]: f[5] for f in filhos}
    assert papeis[filho1] == "pai"
    assert papeis[filho2] == "pai"


def test_progenie_mae(um):
    vaca_id = _make_animal(um, sexo="F")
    filho = _make_animal(um, sexo="M", mae_id=vaca_id)
    filhos = animal_repository.get_progenie_by_touro(vaca_id, um)
    assert any(f[0] == filho and f[5] == "mae" for f in filhos)


def test_progenie_isolamento(dois):
    uid_a, uid_b = dois
    touro_a = _make_animal(uid_a, sexo="M")
    # filho pertence a uid_b mas com pai_id de uid_a (não deve aparecer)
    _make_animal(uid_b, sexo="F", pai_id=touro_a)
    filhos = animal_repository.get_progenie_by_touro(touro_a, uid_a)
    # Como o filho tem user_id = uid_b, não aparece no resultado de uid_a
    assert filhos == []


# ── Histórico reprodutivo (vw_historico_vaca) ─────────────────────────────────

def test_historico_vaca_sem_eventos(um):
    vaca_id = _make_animal(um, sexo="F")
    stats = animal_repository.get_historico_reproducao(vaca_id, um)
    # Vaca sem eventos: view não retorna linha
    assert stats is None


def test_historico_vaca_com_eventos(um):
    vaca_id = _make_animal(um, sexo="F")
    reproducao_repository.insert_reproducao(um, vaca_id, None, "T1", "2024-01-01", "2024-10-01", "vivo")
    reproducao_repository.insert_reproducao(um, vaca_id, None, "T2", "2023-06-01", None, "aborto")
    stats = animal_repository.get_historico_reproducao(vaca_id, um)
    assert stats is not None
    assert stats[1] == 2   # total_coberturas
    assert stats[2] == 1   # partos_vivos


# ── get_animais_ativos_por_sexo ───────────────────────────────────────────────

def test_get_animais_ativos_por_sexo(um):
    m1 = _make_animal(um, sexo="M")
    m2 = _make_animal(um, sexo="M")
    f1 = _make_animal(um, sexo="F")
    machos = animal_repository.get_animais_ativos_por_sexo(um, "M")
    femeas = animal_repository.get_animais_ativos_por_sexo(um, "F")
    ids_machos = [r[0] for r in machos]
    ids_femeas = [r[0] for r in femeas]
    assert m1 in ids_machos and m2 in ids_machos
    assert f1 in ids_femeas
    assert f1 not in ids_machos


# ── Rotas HTTP ────────────────────────────────────────────────────────────────

def test_rota_progenie_requer_login(app):
    with app.test_client() as client:
        uid = _make_user()
        aid = _make_animal(uid)
        r = client.get(f"/animais/{aid}/progenie")
        assert r.status_code in (302, 401)
        _purge(uid)


def test_rota_progenie_logado(app):
    with app.test_client() as client:
        uid = _make_user()
        aid = _make_animal(uid)
        _login(client, uid)
        r = client.get(f"/animais/{aid}/progenie")
        assert r.status_code == 200
        _purge(uid)


def test_rota_reproducao_logado(app):
    with app.test_client() as client:
        uid = _make_user()
        vaca_id = _make_animal(uid, sexo="F")
        _login(client, uid)
        r = client.get(f"/animais/{vaca_id}/reproducao")
        assert r.status_code == 200
        _purge(uid)


def test_registrar_reproducao_post(app):
    with app.test_client() as client:
        uid = _make_user()
        vaca_id = _make_animal(uid, sexo="F")
        _login(client, uid)
        r = client.post("/reproducao", data={
            "vaca_id": vaca_id,
            "touro_id": "",
            "touro_externo": "Touro Externo Teste",
            "data_cobertura": "2024-03-15",
            "data_parto": "",
            "resultado": "aborto",
        }, follow_redirects=True)
        assert r.status_code == 200
        eventos = reproducao_repository.get_reproducao_by_vaca(vaca_id, uid)
        assert len(eventos) == 1
        _purge(uid)


def test_rota_ranking_touros_logado(app):
    with app.test_client() as client:
        uid = _make_user()
        _login(client, uid)
        r = client.get("/rebanho/ranking-touros")
        assert r.status_code == 200
        _purge(uid)
