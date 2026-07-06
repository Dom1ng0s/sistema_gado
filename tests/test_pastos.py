"""
Testes da Entrega 1 — Gestão de Pastos.
Repositório: pasto_repository | Blueprint: pastos_bp
"""
import pytest
import itertools
from werkzeug.security import generate_password_hash
import db_config as dbc
from repositories import pasto_repository

_seq = itertools.count(5000)


def _n():
    return next(_seq)


# ── helpers de banco ──────────────────────────────────────────────────────────

def _make_user():
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
        (f"pu_{_n()}", generate_password_hash("x")),
    )
    uid = cur.lastrowid
    conn.commit(); cur.close(); conn.close()
    return uid


def _make_animal(user_id):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id)"
        " VALUES (%s, 'M', '2024-01-01', 1000, %s)",
        (f"PA{_n()}", user_id),
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


def _fetch_one(sql, params):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close(); conn.close()
    return row


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


# ── CRUD pastos ───────────────────────────────────────────────────────────────

def test_insert_e_get_pasto(um):
    pid = pasto_repository.insert_pasto(um, "Pasto Teste", 100.0, "Brachiaria", 50.0)
    assert pid is not None
    pastos = pasto_repository.get_pastos(um)
    assert any(p[0] == pid and p[1] == "Pasto Teste" for p in pastos)


def test_get_pasto_by_id_correto(um):
    pid = pasto_repository.insert_pasto(um, "P Correto", None, None, None)
    p = pasto_repository.get_pasto_by_id(pid, um)
    assert p is not None
    assert p[1] == "P Correto"


def test_get_pasto_by_id_usuario_errado_retorna_none(dois):
    uid_a, uid_b = dois
    pid = pasto_repository.insert_pasto(uid_a, "Pasto A", None, None, None)
    assert pasto_repository.get_pasto_by_id(pid, uid_b) is None


# ── CRUD módulos ──────────────────────────────────────────────────────────────

def test_insert_modulo_e_buscar_por_pasto(um):
    pid = pasto_repository.insert_pasto(um, "Pasto M", None, None, 30.0)
    mid = pasto_repository.insert_modulo(pid, um, "Módulo 1", 20.0, 15.0)
    assert mid is not None
    modulos = pasto_repository.get_modulos_by_pasto(pid, um)
    assert any(m[0] == mid and m[1] == "Módulo 1" for m in modulos)


def test_get_modulo_usuario_errado_retorna_none(dois):
    uid_a, uid_b = dois
    pid = pasto_repository.insert_pasto(uid_a, "Pasto X", None, None, None)
    mid = pasto_repository.insert_modulo(pid, uid_a, "Mod X", None, None)
    assert pasto_repository.get_modulo_by_id(mid, uid_b) is None


# ── ocupações ─────────────────────────────────────────────────────────────────

def test_iniciar_ocupacao_cria_registros(um):
    aid = _make_animal(um)
    pid = pasto_repository.insert_pasto(um, "Pasto Oc", None, None, 10.0)
    mid = pasto_repository.insert_modulo(pid, um, "Mod Oc", None, 10.0)

    oc_id = pasto_repository.iniciar_ocupacao(mid, um, "2024-03-01", [aid])
    assert oc_id is not None

    row = _fetch_one("SELECT COUNT(*) FROM ocupacao_animais WHERE ocupacao_id = %s", (oc_id,))
    assert row[0] == 1


def test_encerrar_ocupacao_libera_modulo(um):
    aid = _make_animal(um)
    pid = pasto_repository.insert_pasto(um, "Pasto Enc", None, None, 10.0)
    mid = pasto_repository.insert_modulo(pid, um, "Mod Enc", None, 10.0)
    oc_id = pasto_repository.iniciar_ocupacao(mid, um, "2024-03-01", [aid])

    assert pasto_repository.get_ocupacao_ativa(mid, um) is not None
    ok = pasto_repository.encerrar_ocupacao(oc_id, um, "2024-06-01")
    assert ok is True
    assert pasto_repository.get_ocupacao_ativa(mid, um) is None


def test_encerrar_ocupacao_usuario_errado_retorna_false(dois):
    uid_a, uid_b = dois
    aid = _make_animal(uid_a)
    pid = pasto_repository.insert_pasto(uid_a, "Pasto Seg", None, None, None)
    mid = pasto_repository.insert_modulo(pid, uid_a, "Mod Seg", None, None)
    oc_id = pasto_repository.iniciar_ocupacao(mid, uid_a, "2024-03-01", [aid])

    assert pasto_repository.encerrar_ocupacao(oc_id, uid_b, "2024-06-01") is False
    assert pasto_repository.get_ocupacao_ativa(mid, uid_a) is not None


def test_get_ocupacao_ativa_retorna_none_sem_ocupacao(um):
    pid = pasto_repository.insert_pasto(um, "Pasto Vazio", None, None, None)
    mid = pasto_repository.insert_modulo(pid, um, "Mod Vazio", None, None)
    assert pasto_repository.get_ocupacao_ativa(mid, um) is None


# ── views ─────────────────────────────────────────────────────────────────────

def test_modulo_ocupado_aparece_em_ocupacao_atual(um):
    aid = _make_animal(um)
    pid = pasto_repository.insert_pasto(um, "P View", None, None, 5.0)
    mid = pasto_repository.insert_modulo(pid, um, "M View", None, 5.0)
    pasto_repository.iniciar_ocupacao(mid, um, "2024-03-01", [aid])

    atual = pasto_repository.get_ocupacao_atual(um)
    assert any(row[0] == mid for row in atual)


def test_modulo_ocupado_nao_aparece_em_dias_descanso(um):
    aid = _make_animal(um)
    pid = pasto_repository.insert_pasto(um, "P Oc2", None, None, 5.0)
    mid = pasto_repository.insert_modulo(pid, um, "M Oc2", None, 5.0)
    pasto_repository.iniciar_ocupacao(mid, um, "2024-03-01", [aid])

    descanso = pasto_repository.get_dias_descanso(um)
    assert not any(row[0] == mid for row in descanso)


def test_modulo_encerrado_aparece_em_dias_descanso(um):
    aid = _make_animal(um)
    pid = pasto_repository.insert_pasto(um, "P Desc", None, None, 5.0)
    mid = pasto_repository.insert_modulo(pid, um, "M Desc", None, 5.0)
    oc_id = pasto_repository.iniciar_ocupacao(mid, um, "2024-01-01", [aid])
    pasto_repository.encerrar_ocupacao(oc_id, um, "2024-02-01")

    descanso = pasto_repository.get_dias_descanso(um)
    assert any(row[0] == mid for row in descanso)


def test_get_gmd_por_modulo_calcula_gmd_do_animal_ocupante(um):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id) "
        "VALUES (%s, 'M', '2024-01-01', 1000, %s)",
        (f"PGMD{_n()}", um),
    )
    aid = cur.lastrowid
    cur.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, '2024-01-01', 300)", (aid,))
    cur.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, '2024-01-11', 310)", (aid,))
    conn.commit(); cur.close(); conn.close()

    pid = pasto_repository.insert_pasto(um, "P GMD", None, None, 5.0)
    mid = pasto_repository.insert_modulo(pid, um, "M GMD", None, 5.0)
    pasto_repository.iniciar_ocupacao(mid, um, "2024-01-01", [aid])

    ranking = pasto_repository.get_gmd_por_modulo(um)
    row = next(r for r in ranking if r[0] == mid)
    # modulo_id, modulo_nome, pasto_id, qtd_animais, gmd_medio
    assert row[3] == 1
    assert float(row[4]) == pytest.approx(1.0)


# ── rotas HTTP ────────────────────────────────────────────────────────────────

def test_get_pastos_redireciona_sem_login(client):
    resp = client.get('/pastos')
    assert resp.status_code in (301, 302)


def test_get_pastos_autenticado_retorna_200(client):
    client.post('/login', data={'username': 'testuser', 'password': '123'})
    resp = client.get('/pastos')
    assert resp.status_code == 200


def test_post_pasto_cria_e_redireciona(client):
    client.post('/login', data={'username': 'testuser', 'password': '123'})
    resp = client.post('/pastos', data={
        'nome': 'Pasto HTTP Teste',
        'area_hectares': '50',
        'forrageira': 'Brachiaria',
        'capacidade_ua': '20',
    }, follow_redirects=False)
    assert resp.status_code in (301, 302)


def test_get_pastos_gmd_retorna_200(client):
    client.post('/login', data={'username': 'testuser', 'password': '123'})
    resp = client.get('/pastos/gmd')
    assert resp.status_code == 200


# ── rotas HTTP de mutação (módulos/ocupações) ──────────────────────────────────

def test_post_criar_modulo_via_http(app):
    """POST /pastos/<id>/modulos cria o módulo e redireciona para o detalhe do pasto."""
    with app.test_client() as client:
        uid = _make_user()
        _login(client, uid)
        pid = pasto_repository.insert_pasto(uid, "Pasto Modulo HTTP", None, None, 30.0)

        resp = client.post(f'/pastos/{pid}/modulos', data={
            'nome': 'Módulo HTTP', 'area_hectares': '10', 'capacidade_ua': '20',
        }, follow_redirects=True)

        assert resp.status_code == 200
        assert 'Módulo HTTP'.encode('utf-8') in resp.data
        _purge(uid)


def test_post_criar_modulo_pasto_alheio_nao_cria(app):
    """POST /pastos/<id_de_A>/modulos como B não deve criar módulo em pasto de A."""
    with app.test_client() as client:
        uid_a, uid_b = _make_user(), _make_user()
        pid_a = pasto_repository.insert_pasto(uid_a, "Pasto de A", None, None, None)
        _login(client, uid_b)

        client.post(f'/pastos/{pid_a}/modulos', data={'nome': 'Invasor'}, follow_redirects=True)

        modulos_a = pasto_repository.get_modulos_by_pasto(pid_a, uid_a)
        assert not any(m[1] == 'Invasor' for m in modulos_a)
        _purge(uid_a)
        _purge(uid_b)


def test_post_ocupar_modulo_via_http(app):
    """POST /modulos/<id>/ocupar inicia ocupação com os animais selecionados."""
    with app.test_client() as client:
        uid = _make_user()
        aid = _make_animal(uid)
        _login(client, uid)
        pid = pasto_repository.insert_pasto(uid, "Pasto Ocupar HTTP", None, None, 10.0)
        mid = pasto_repository.insert_modulo(pid, uid, "Modulo Ocupar HTTP", None, 10.0)

        resp = client.post(f'/modulos/{mid}/ocupar', data={
            'data_entrada': '2024-03-01', 'animal_ids[]': [str(aid)],
        }, follow_redirects=True)

        assert resp.status_code == 200
        assert pasto_repository.get_ocupacao_ativa(mid, uid) is not None
        _purge(uid)


def test_post_ocupar_modulo_alheio_nao_inicia_ocupacao(app):
    """POST /modulos/<id_de_A>/ocupar como B não deve criar ocupação no módulo de A."""
    with app.test_client() as client:
        uid_a, uid_b = _make_user(), _make_user()
        aid_a = _make_animal(uid_a)
        pid_a = pasto_repository.insert_pasto(uid_a, "Pasto Seg2", None, None, 10.0)
        mid_a = pasto_repository.insert_modulo(pid_a, uid_a, "Mod Seg2", None, 10.0)
        _login(client, uid_b)

        client.post(f'/modulos/{mid_a}/ocupar', data={
            'data_entrada': '2024-03-01', 'animal_ids[]': [str(aid_a)],
        }, follow_redirects=True)

        assert pasto_repository.get_ocupacao_ativa(mid_a, uid_a) is None
        _purge(uid_a)
        _purge(uid_b)


def test_post_encerrar_ocupacao_via_http(app):
    """POST /ocupacoes/<id>/encerrar grava data_saida e libera o módulo."""
    with app.test_client() as client:
        uid = _make_user()
        aid = _make_animal(uid)
        _login(client, uid)
        pid = pasto_repository.insert_pasto(uid, "Pasto Encerrar HTTP", None, None, 10.0)
        mid = pasto_repository.insert_modulo(pid, uid, "Modulo Encerrar HTTP", None, 10.0)
        oc_id = pasto_repository.iniciar_ocupacao(mid, uid, "2024-01-01", [aid])

        resp = client.post(f'/ocupacoes/{oc_id}/encerrar', data={'data_saida': '2024-02-01'},
                            follow_redirects=True)

        assert resp.status_code == 200
        assert pasto_repository.get_ocupacao_ativa(mid, uid) is None
        _purge(uid)


def test_post_encerrar_ocupacao_alheia_nao_altera(app):
    """POST /ocupacoes/<id_de_A>/encerrar como B não deve encerrar a ocupação de A."""
    with app.test_client() as client:
        uid_a, uid_b = _make_user(), _make_user()
        aid_a = _make_animal(uid_a)
        pid_a = pasto_repository.insert_pasto(uid_a, "Pasto Seg3", None, None, 10.0)
        mid_a = pasto_repository.insert_modulo(pid_a, uid_a, "Mod Seg3", None, 10.0)
        oc_id = pasto_repository.iniciar_ocupacao(mid_a, uid_a, "2024-01-01", [aid_a])
        _login(client, uid_b)

        client.post(f'/ocupacoes/{oc_id}/encerrar', data={'data_saida': '2024-02-01'},
                    follow_redirects=True)

        assert pasto_repository.get_ocupacao_ativa(mid_a, uid_a) is not None
        _purge(uid_a)
        _purge(uid_b)
