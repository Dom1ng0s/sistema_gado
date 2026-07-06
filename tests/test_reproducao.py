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

def test_registrar_parto_com_bezerro_cria_ambos(um):
    vaca_id = _make_animal(um, sexo="F")
    brinco_bezerro = f"BEZ{_n()}"
    rep_id, bezerro_id = reproducao_repository.registrar_parto_com_bezerro(
        um, vaca_id, None, None, "2024-01-01", "2024-10-15", "vivo",
        brinco_bezerro=brinco_bezerro, sexo_bezerro="F",
    )
    assert rep_id is not None
    assert bezerro_id is not None

    bezerro = animal_repository.get_animal_by_id(bezerro_id, um)
    assert bezerro is not None
    assert bezerro[1] == brinco_bezerro  # índice 1 = brinco

    eventos = reproducao_repository.get_reproducao_by_vaca(vaca_id, um)
    assert any(e[0] == rep_id for e in eventos)


def test_registrar_parto_com_bezerro_brinco_duplicado_faz_rollback_da_reproducao(um):
    """Cenário de falha do #18: se o insert do bezerro falha (brinco duplicado),
    o insert da reprodução tem que ser desfeito junto — não pode sobrar um
    registro de 'parto vivo' sem o bezerro correspondente."""
    vaca_id = _make_animal(um, sexo="F")
    brinco_dup = f"DUP{_n()}"
    _make_animal(um, sexo="M", brinco=brinco_dup)  # já ocupa o brinco

    eventos_antes = reproducao_repository.get_reproducao_by_vaca(vaca_id, um)

    with pytest.raises(Exception):
        reproducao_repository.registrar_parto_com_bezerro(
            um, vaca_id, None, None, "2024-01-01", "2024-10-15", "vivo",
            brinco_bezerro=brinco_dup, sexo_bezerro="F",
        )

    eventos_depois = reproducao_repository.get_reproducao_by_vaca(vaca_id, um)
    assert len(eventos_depois) == len(eventos_antes)  # nada foi commitado


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


def test_registrar_reproducao_post_parto_vivo_cria_bezerro(app):
    with app.test_client() as client:
        uid = _make_user()
        vaca_id = _make_animal(uid, sexo="F")
        brinco_bezerro = f"BEZHTTP{_n()}"
        _login(client, uid)
        r = client.post("/reproducao", data={
            "vaca_id": vaca_id,
            "touro_id": "",
            "touro_externo": "Touro Externo Teste",
            "data_cobertura": "2024-01-01",
            "data_parto": "2024-10-15",
            "resultado": "vivo",
            "brinco_bezerro": brinco_bezerro,
            "sexo_bezerro": "F",
        }, follow_redirects=True)
        assert r.status_code == 200
        assert animal_repository.check_brinco_exists(brinco_bezerro, uid) is True
        _purge(uid)


def test_rota_ranking_touros_logado(app):
    with app.test_client() as client:
        uid = _make_user()
        _login(client, uid)
        r = client.get("/rebanho/ranking-touros")
        assert r.status_code == 200
        _purge(uid)


# ── 5.3 — Diagnóstico de prenhez + data prevista de parto ────────────────────

def test_insert_reproducao_calcula_parto_previsto(um):
    """data_parto_prevista = data_cobertura + 285 dias."""
    from datetime import date, timedelta
    vaca_id = _make_animal(um, sexo="F")
    reproducao_repository.insert_reproducao(
        um, vaca_id, None, "Touro X", "2026-01-01", None, "aborto"
    )
    eventos = reproducao_repository.get_reproducao_by_vaca(vaca_id, um)
    # índice 8 = data_parto_prevista
    prevista = eventos[0][8]
    assert prevista == date(2026, 1, 1) + timedelta(days=285)


def test_update_diagnostico_positivo(um):
    """update_diagnostico salva DG positivo e data."""
    vaca_id = _make_animal(um, sexo="F")
    rid = reproducao_repository.insert_reproducao(
        um, vaca_id, None, "T", "2026-02-01", None, "aborto"
    )
    ok = reproducao_repository.update_diagnostico(rid, um, "positivo", "2026-02-28")
    assert ok is True
    eventos = reproducao_repository.get_reproducao_by_vaca(vaca_id, um)
    assert eventos[0][6] == "positivo"           # diagnostico
    assert str(eventos[0][7]) == "2026-02-28"    # data_diagnostico


def test_update_diagnostico_outro_usuario_nao_altera(dois):
    """update_diagnostico de usuário errado não persiste."""
    uid_a, uid_b = dois
    vaca_id = _make_animal(uid_a, sexo="F")
    rid = reproducao_repository.insert_reproducao(
        uid_a, vaca_id, None, "T", "2026-03-01", None, "aborto"
    )
    ok = reproducao_repository.update_diagnostico(rid, uid_b, "positivo", "2026-03-15")
    assert ok is False
    eventos = reproducao_repository.get_reproducao_by_vaca(vaca_id, uid_a)
    assert eventos[0][6] == "pendente"


def test_get_partos_previstos_so_retorna_dg_positivo(um):
    """get_partos_previstos filtra apenas DG positivo com parto não ocorrido."""
    from datetime import date, timedelta
    vaca_id = _make_animal(um, sexo="F")
    rid = reproducao_repository.insert_reproducao(
        um, vaca_id, None, "T", date.today().isoformat(), None, "aborto"
    )
    # Sem DG — não deve aparecer
    assert reproducao_repository.get_partos_previstos(um, dias=400) == []

    reproducao_repository.update_diagnostico(rid, um, "positivo", date.today().isoformat())
    previstos = reproducao_repository.get_partos_previstos(um, dias=400)
    assert len(previstos) == 1


def test_rota_diagnostico_post(app):
    """Rota POST /reproducao/<id>/diagnostico persiste DG via HTTP."""
    with app.test_client() as client:
        from datetime import date
        uid = _make_user()
        vaca_id = _make_animal(uid, sexo="F")
        rid = reproducao_repository.insert_reproducao(
            uid, vaca_id, None, "T", "2026-05-01", None, "aborto"
        )
        _login(client, uid)
        r = client.post(f"/reproducao/{rid}/diagnostico", data={
            "vaca_id": vaca_id,
            "diagnostico": "negativo",
            "data_diagnostico": "2026-05-28",
        }, follow_redirects=True)
        assert r.status_code == 200
        eventos = reproducao_repository.get_reproducao_by_vaca(vaca_id, uid)
        assert eventos[0][6] == "negativo"
        _purge(uid)


def test_rota_diagnostico_post_vaca_alheia_nao_altera(app):
    """POST /reproducao/<id>/diagnostico como B não deve alterar DG de vaca de A."""
    with app.test_client() as client:
        uid_a, uid_b = _make_user(), _make_user()
        vaca_id = _make_animal(uid_a, sexo="F")
        rid = reproducao_repository.insert_reproducao(
            uid_a, vaca_id, None, "T", "2026-05-01", None, "aborto"
        )
        _login(client, uid_b)
        r = client.post(f"/reproducao/{rid}/diagnostico", data={
            "vaca_id": vaca_id,
            "diagnostico": "positivo",
            "data_diagnostico": "2026-05-28",
        }, follow_redirects=True)
        assert r.status_code == 200
        eventos = reproducao_repository.get_reproducao_by_vaca(vaca_id, uid_a)
        assert eventos[0][6] == "pendente"
        _purge(uid_a)
        _purge(uid_b)


def test_registrar_reproducao_post_vaca_alheia_nao_cria(app):
    """POST /reproducao com vaca_id de outro usuário não deve criar o evento reprodutivo."""
    with app.test_client() as client:
        uid_a, uid_b = _make_user(), _make_user()
        vaca_id = _make_animal(uid_a, sexo="F")
        _login(client, uid_b)
        r = client.post("/reproducao", data={
            "vaca_id": vaca_id,
            "data_cobertura": "2026-05-01",
            "resultado": "aborto",
            "touro_externo": "Touro X",
        }, follow_redirects=True)
        assert r.status_code == 200
        eventos = reproducao_repository.get_reproducao_by_vaca(vaca_id, uid_a)
        assert eventos == []
        _purge(uid_a)
        _purge(uid_b)


def test_pagina_reproducao_mostra_data_prevista(app):
    """Página de reprodução exibe data_parto_prevista calculada quando DG é positivo.

    A data prevista só é exibida com diagnóstico positivo (ver animal_reproducao.html) —
    sem DG, o parto ainda pode não ocorrer, então a UI não mostra uma previsão.
    """
    from datetime import date, timedelta
    with app.test_client() as client:
        uid = _make_user()
        vaca_id = _make_animal(uid, sexo="F")
        rep_id = reproducao_repository.insert_reproducao(
            uid, vaca_id, None, "T", "2026-06-01", None, "aborto"
        )
        reproducao_repository.update_diagnostico(rep_id, uid, "positivo", "2026-07-01")
        _login(client, uid)
        r = client.get(f"/animais/{vaca_id}/reproducao")
        assert r.status_code == 200
        esperado = (date(2026, 6, 1) + timedelta(days=285)).isoformat()
        assert esperado.encode() in r.data
        _purge(uid)
