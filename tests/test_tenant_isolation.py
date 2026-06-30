"""
Testes de isolamento multi-tenant ao nível HTTP.
Verifica que as rotas respeitam o user_id da sessão e não permitem
leitura nem mutação de dados pertencentes a outro usuário.
"""
import pytest
import itertools
from werkzeug.security import generate_password_hash
import db_config as dbc

_seq = itertools.count(3000)


def _n():
    return next(_seq)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_user():
    n = _n()
    username = f"ti_{n}"
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
        (username, generate_password_hash("senha123")),
    )
    uid = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return uid, username


def _make_animal(user_id, brinco):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id)"
        " VALUES (%s, 'M', '2024-01-01', 1000, %s)",
        (brinco, user_id),
    )
    aid = cur.lastrowid
    cur.execute(
        "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, '2024-01-01', 300)",
        (aid,),
    )
    conn.commit()
    cur.close()
    conn.close()
    return aid


def _purge(user_id):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    for sql in [
        "DELETE p FROM pesagens p JOIN animais a ON p.animal_id = a.id WHERE a.user_id = %s",
        "DELETE m FROM medicacoes m JOIN animais a ON m.animal_id = a.id WHERE a.user_id = %s",
        "DELETE FROM animais WHERE user_id = %s",
        "DELETE FROM custos_operacionais WHERE user_id = %s",
        "DELETE FROM configuracoes WHERE user_id = %s",
        "DELETE FROM usuarios WHERE id = %s",
    ]:
        cur.execute(sql, (user_id,))
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()
    cur.close()
    conn.close()


def _fetch_one(sql, params):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def _login(client, username):
    return client.post(
        "/login",
        data={"username": username, "password": "senha123"},
        follow_redirects=True,
    )


# ── Fixture central ──────────────────────────────────────────────────────────

@pytest.fixture
def cenario(app):
    """
    Cria usuário A com um animal e usuário B logado no client.
    Yield: (client_b, animal_id_de_a, brinco_de_a, uid_a, uid_b)
    """
    n = _n()
    uid_a, user_a = _make_user()
    uid_b, user_b = _make_user()
    brinco_a = f"BRINCO-A-{n}"
    aid = _make_animal(uid_a, brinco_a)

    client_b = app.test_client()
    _login(client_b, user_b)

    yield client_b, aid, brinco_a, uid_a, uid_b

    _purge(uid_a)
    _purge(uid_b)


# ── Testes ───────────────────────────────────────────────────────────────────

def test_painel_nao_exibe_animais_de_outro_usuario(cenario):
    """O painel de B não deve listar animais cadastrados por A."""
    client_b, aid, brinco_a, uid_a, uid_b = cenario
    resp = client_b.get("/painel")
    assert brinco_a.encode() not in resp.data


def test_detalhes_animal_alheio_redireciona_sem_expor_dados(cenario):
    """GET /animal/<id_de_A> como B deve redirecionar para o painel."""
    client_b, aid, brinco_a, uid_a, uid_b = cenario
    resp = client_b.get(f"/animal/{aid}", follow_redirects=True)
    assert brinco_a.encode() not in resp.data


def test_vender_animal_alheio_nao_altera_data_venda(cenario):
    """POST /vender/<id_de_A> como B não deve gravar data_venda no banco."""
    client_b, aid, brinco_a, uid_a, uid_b = cenario
    client_b.post(
        f"/vender/{aid}",
        data={"data_venda": "2024-06-01", "peso_venda": "500", "valor_arroba": "300"},
    )
    row = _fetch_one("SELECT data_venda FROM animais WHERE id = %s", (aid,))
    assert row[0] is None


def test_pesar_animal_alheio_nao_cria_pesagem(cenario):
    """POST /pesar/<id_de_A> como B não deve inserir uma nova pesagem."""
    client_b, aid, brinco_a, uid_a, uid_b = cenario
    antes = _fetch_one("SELECT COUNT(*) FROM pesagens WHERE animal_id = %s", (aid,))[0]

    client_b.post(f"/pesar/{aid}", data={"data_pesagem": "2024-06-01", "peso": "400"})

    depois = _fetch_one("SELECT COUNT(*) FROM pesagens WHERE animal_id = %s", (aid,))[0]
    assert depois == antes


def test_medicar_animal_alheio_nao_cria_medicacao(cenario):
    """POST /medicar/<id_de_A> como B não deve inserir medicação."""
    client_b, aid, brinco_a, uid_a, uid_b = cenario
    antes = _fetch_one("SELECT COUNT(*) FROM medicacoes WHERE animal_id = %s", (aid,))[0]

    client_b.post(
        f"/medicar/{aid}",
        data={"data_aplicacao": "2024-06-01", "nome": "Ivermectina", "custo": "50", "obs": ""},
    )

    depois = _fetch_one("SELECT COUNT(*) FROM medicacoes WHERE animal_id = %s", (aid,))[0]
    assert depois == antes


def test_excluir_animal_alheio_nao_marca_deleted_at(cenario):
    """POST /excluir_animal/<id_de_A> como B não deve marcar deleted_at."""
    client_b, aid, brinco_a, uid_a, uid_b = cenario
    client_b.post(f"/excluir_animal/{aid}")
    row = _fetch_one("SELECT deleted_at FROM animais WHERE id = %s", (aid,))
    assert row[0] is None


def test_restaurar_animal_alheio_nao_altera_deleted_at(cenario):
    """POST /restaurar_animal/<id_de_A> como B não deve limpar deleted_at."""
    client_b, aid, brinco_a, uid_a, uid_b = cenario
    # Soft-delete direto no banco para simular animal na lixeira de A
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE animais SET deleted_at = NOW() WHERE id = %s", (aid,))
    conn.commit()
    cur.close()
    conn.close()

    client_b.post(f"/restaurar_animal/{aid}")

    row = _fetch_one("SELECT deleted_at FROM animais WHERE id = %s", (aid,))
    assert row[0] is not None  # deve continuar deletado
