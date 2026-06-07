"""
Testes da Entrega 3 — Estoque Virtual.
Repositório: estoque_repository | Blueprint: estoque_bp
"""
import pytest
import itertools
from werkzeug.security import generate_password_hash
import db_config as dbc
from repositories import estoque_repository

_seq = itertools.count(9000)


def _n():
    return next(_seq)


# ── helpers de banco ──────────────────────────────────────────────────────────

def _make_user():
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
        (f"est_{_n()}", generate_password_hash("x")),
    )
    uid = cur.lastrowid
    conn.commit(); cur.close(); conn.close()
    return uid


def _purge(user_id):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    for sql in [
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


# ── CRUD produtos ─────────────────────────────────────────────────────────────

def test_insert_e_get_produto(um):
    pid = estoque_repository.insert_produto(um, "Ivermectina 1%", "ml", "medicamento", 100.0)
    assert pid is not None
    produtos = estoque_repository.get_produtos(um)
    assert any(p[0] == pid and p[2] == "Ivermectina 1%" for p in produtos)


def test_get_produto_by_id(um):
    pid = estoque_repository.insert_produto(um, "Vacina aftosa", "dose", "vacina", 10.0)
    produto = estoque_repository.get_produto_by_id(pid, um)
    assert produto is not None
    assert produto[2] == "Vacina aftosa"
    assert produto[3] == "dose"
    assert produto[4] == "vacina"


def test_produto_saldo_inicial_zero(um):
    pid = estoque_repository.insert_produto(um, "Sal mineral", "kg", "mineral", 50.0)
    produto = estoque_repository.get_produto_by_id(pid, um)
    assert float(produto[8]) == 0.0


# ── Movimentações e saldo ─────────────────────────────────────────────────────

def test_entrada_aumenta_saldo(um):
    pid = estoque_repository.insert_produto(um, "Antibiótico", "ml", "medicamento", 0)
    estoque_repository.insert_movimentacao(um, pid, 'entrada', 500.0, 1.50, "Compra NF001", "2024-05-01")
    saldo = estoque_repository.get_saldo_atual(pid, um)
    assert saldo == pytest.approx(500.0)


def test_saida_reduz_saldo(um):
    pid = estoque_repository.insert_produto(um, "Vermífugo", "ml", "medicamento", 0)
    estoque_repository.insert_movimentacao(um, pid, 'entrada', 1000.0, None, None, "2024-05-01")
    estoque_repository.insert_movimentacao(um, pid, 'saida', 300.0, None, "Aplicação lote A", "2024-05-10")
    saldo = estoque_repository.get_saldo_atual(pid, um)
    assert saldo == pytest.approx(700.0)


def test_multiplas_movimentacoes(um):
    pid = estoque_repository.insert_produto(um, "Vitamina ADE", "ml", "suplemento", 0)
    estoque_repository.insert_movimentacao(um, pid, 'entrada', 2000.0, 0.80, None, "2024-01-01")
    estoque_repository.insert_movimentacao(um, pid, 'saida',   500.0, None, None, "2024-02-01")
    estoque_repository.insert_movimentacao(um, pid, 'entrada', 1000.0, 0.75, None, "2024-03-01")
    estoque_repository.insert_movimentacao(um, pid, 'saida',   200.0, None, None, "2024-04-01")
    saldo = estoque_repository.get_saldo_atual(pid, um)
    assert saldo == pytest.approx(2300.0)


def test_get_movimentacoes_ordenadas(um):
    pid = estoque_repository.insert_produto(um, "Produto Ordem", "un", "outro", 0)
    estoque_repository.insert_movimentacao(um, pid, 'entrada', 100, None, None, "2024-01-01")
    estoque_repository.insert_movimentacao(um, pid, 'saida',    10, None, None, "2024-03-01")
    movs = estoque_repository.get_movimentacoes_by_produto(pid, um)
    assert len(movs) == 2
    # Mais recente primeiro
    assert str(movs[0][5]) > str(movs[1][5])


# ── Flag abaixo_minimo ────────────────────────────────────────────────────────

def test_abaixo_minimo_ativo(um):
    pid = estoque_repository.insert_produto(um, "Produto Mínimo", "un", "outro", 100.0)
    estoque_repository.insert_movimentacao(um, pid, 'entrada', 50.0, None, None, "2024-01-01")
    produto = estoque_repository.get_produto_by_id(pid, um)
    assert produto[9] == 1  # abaixo_minimo


def test_abaixo_minimo_nao_ativo(um):
    pid = estoque_repository.insert_produto(um, "Produto OK", "un", "outro", 100.0)
    estoque_repository.insert_movimentacao(um, pid, 'entrada', 200.0, None, None, "2024-01-01")
    produto = estoque_repository.get_produto_by_id(pid, um)
    assert produto[9] == 0  # saldo OK


# ── Isolamento multi-tenant ───────────────────────────────────────────────────

def test_isolamento_produtos(dois):
    uid_a, uid_b = dois
    pid_a = estoque_repository.insert_produto(uid_a, "Produto A", "ml", "medicamento", 0)
    pid_b = estoque_repository.insert_produto(uid_b, "Produto B", "kg", "mineral", 0)
    prods_a = [p[0] for p in estoque_repository.get_produtos(uid_a)]
    prods_b = [p[0] for p in estoque_repository.get_produtos(uid_b)]
    assert pid_a in prods_a and pid_b not in prods_a
    assert pid_b in prods_b and pid_a not in prods_b


def test_get_produto_by_id_isolamento(dois):
    uid_a, uid_b = dois
    pid_a = estoque_repository.insert_produto(uid_a, "Exclusivo A", "ml", "vacina", 0)
    assert estoque_repository.get_produto_by_id(pid_a, uid_b) is None


# ── Rotas HTTP ────────────────────────────────────────────────────────────────

def test_lista_estoque_requer_login(app):
    with app.test_client() as client:
        r = client.get("/estoque")
        assert r.status_code in (302, 401)


def test_lista_estoque_logado(app):
    with app.test_client() as client:
        uid = _make_user()
        _login(client, uid)
        r = client.get("/estoque")
        assert r.status_code == 200
        _purge(uid)


def test_cadastrar_produto_via_post(app):
    with app.test_client() as client:
        uid = _make_user()
        _login(client, uid)
        r = client.post("/estoque", data={
            "nome": "Produto Via POST",
            "unidade": "ml",
            "categoria": "medicamento",
            "estoque_minimo": "50",
        }, follow_redirects=True)
        assert r.status_code == 200
        produtos = estoque_repository.get_produtos(uid)
        assert any(p[2] == "Produto Via POST" for p in produtos)
        _purge(uid)


def test_detalhe_estoque_logado(app):
    with app.test_client() as client:
        uid = _make_user()
        _login(client, uid)
        pid = estoque_repository.insert_produto(uid, "Detalhe Teste", "kg", "mineral", 0)
        r = client.get(f"/estoque/{pid}")
        assert r.status_code == 200
        _purge(uid)


def test_registrar_entrada_via_post(app):
    with app.test_client() as client:
        uid = _make_user()
        _login(client, uid)
        pid = estoque_repository.insert_produto(uid, "Entrada HTTP", "ml", "vacina", 0)
        r = client.post(f"/estoque/{pid}/entrada", data={
            "quantidade": "250",
            "data_mov": "2024-06-01",
            "custo_unitario": "2.50",
            "motivo": "Compra teste",
        }, follow_redirects=True)
        assert r.status_code == 200
        assert estoque_repository.get_saldo_atual(pid, uid) == pytest.approx(250.0)
        _purge(uid)


def test_registrar_saida_saldo_insuficiente(app):
    with app.test_client() as client:
        uid = _make_user()
        _login(client, uid)
        pid = estoque_repository.insert_produto(uid, "Saida Insuficiente", "ml", "medicamento", 0)
        estoque_repository.insert_movimentacao(uid, pid, 'entrada', 100.0, None, None, "2024-01-01")
        r = client.post(f"/estoque/{pid}/saida", data={
            "quantidade": "999",
            "data_mov": "2024-06-01",
            "motivo": "",
        }, follow_redirects=True)
        assert r.status_code == 200
        # Saldo não deve ter mudado
        assert estoque_repository.get_saldo_atual(pid, uid) == pytest.approx(100.0)
        _purge(uid)
