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


# ── 6.1 — Validade de medicamentos ────────────────────────────────────────────

def test_entrada_com_validade(um):
    """Entrada com data_validade é persistida e retorna na listagem."""
    pid = estoque_repository.insert_produto(um, "Vacina Aftosa", "doses", "vacina", 0)
    estoque_repository.insert_movimentacao(
        um, pid, 'entrada', 50.0, 5.0, "Compra jan", "2026-01-10",
        lote_fabricante="L001", data_validade="2026-12-31"
    )
    movs = estoque_repository.get_movimentacoes_by_produto(pid, um)
    assert movs[0][6] == "L001"          # lote_fabricante
    assert str(movs[0][7]) == "2026-12-31"  # data_validade


def test_vw_saldo_estoque_proxima_validade(um):
    """proxima_validade aparece na view vw_saldo_estoque."""
    pid = estoque_repository.insert_produto(um, "Vermífugo", "ml", "medicamento", 0)
    estoque_repository.insert_movimentacao(
        um, pid, 'entrada', 100.0, None, None, "2026-01-01",
        data_validade="2026-06-30"
    )
    produto = estoque_repository.get_produto_by_id(pid, um)
    assert produto[10] is not None     # proxima_validade
    assert str(produto[10]) == "2026-06-30"


def test_get_vencendo_em_dias(um):
    """get_vencendo_em_dias retorna produto com validade próxima."""
    from datetime import date, timedelta
    pid = estoque_repository.insert_produto(um, "Vitamina Venc", "ml", "suplemento", 0)
    proxima = (date.today() + timedelta(days=10)).isoformat()
    estoque_repository.insert_movimentacao(
        um, pid, 'entrada', 20.0, None, None, "2026-01-01",
        data_validade=proxima
    )
    vencendo = estoque_repository.get_vencendo_em_dias(um, dias=30)
    ids = [v[0] for v in vencendo]
    assert pid in ids


def test_entrada_com_validade_via_http(app):
    """POST /estoque/<id>/entrada aceita lote_fabricante e data_validade."""
    with app.test_client() as client:
        uid = _make_user()
        _login(client, uid)
        pid = estoque_repository.insert_produto(uid, "Ivomec Validade", "ml", "medicamento", 0)
        r = client.post(f"/estoque/{pid}/entrada", data={
            "quantidade": "100",
            "data_mov": "2026-01-15",
            "custo_unitario": "3.50",
            "motivo": "Compra com validade",
            "lote_fabricante": "LT-2026",
            "data_validade": "2027-01-15",
        }, follow_redirects=True)
        assert r.status_code == 200
        movs = estoque_repository.get_movimentacoes_by_produto(pid, uid)
        assert movs[0][6] == "LT-2026"
        assert str(movs[0][7]) == "2027-01-15"
        _purge(uid)


# ── 6.3 — Importação via CSV ──────────────────────────────────────────────────

def test_importar_csv_get(app):
    """Página GET de importação carrega corretamente."""
    with app.test_client() as client:
        uid = _make_user()
        _login(client, uid)
        r = client.get("/importar-csv")
        assert r.status_code == 200
        assert b'Importar' in r.data
        _purge(uid)


def test_importar_csv_sucesso(app):
    """CSV válido insere animais e retorna contagem."""
    with app.test_client() as client:
        import io as _io
        uid = _make_user()
        _login(client, uid)
        csv_content = (
            "brinco,sexo,data_compra,peso_kg,valor_arroba,raca\n"
            "IMP-001,M,2026-01-10,300,185.00,Nelore\n"
            "IMP-002,F,2026-01-10,250,175.00,Angus\n"
        ).encode('utf-8')
        r = client.post("/importar-csv", data={
            "arquivo": (_io.BytesIO(csv_content), "animais.csv"),
        }, content_type='multipart/form-data', follow_redirects=True)
        assert r.status_code == 200
        assert b'2' in r.data   # 2 inseridos
        _purge(uid)


def test_importar_csv_coluna_faltando(app):
    """CSV sem coluna obrigatória retorna erro descritivo."""
    with app.test_client() as client:
        import io as _io
        uid = _make_user()
        _login(client, uid)
        csv_content = b"brinco,sexo\nX-001,M\n"
        r = client.post("/importar-csv", data={
            "arquivo": (_io.BytesIO(csv_content), "animais.csv"),
        }, content_type='multipart/form-data', follow_redirects=True)
        assert r.status_code == 200
        assert b'ausentes' in r.data or 'obrigatórias'.encode('utf-8') in r.data
        _purge(uid)


# ── Isolamento multi-tenant — rotas HTTP ─────────────────────────────────────

def test_registrar_entrada_produto_alheio_via_http_nao_registra(app):
    """POST /estoque/<id_de_A>/entrada como B não deve criar movimentação em produto de A."""
    with app.test_client() as client:
        uid_a, uid_b = _make_user(), _make_user()
        pid_a = estoque_repository.insert_produto(uid_a, "Produto de A", "ml", "medicamento", 0)
        _login(client, uid_b)

        client.post(f"/estoque/{pid_a}/entrada", data={
            "quantidade": "100", "data_mov": "2024-06-01",
        }, follow_redirects=True)

        assert estoque_repository.get_saldo_atual(pid_a, uid_a) == pytest.approx(0.0)
        _purge(uid_a)
        _purge(uid_b)


def test_registrar_saida_produto_alheio_via_http_nao_registra(app):
    """POST /estoque/<id_de_A>/saida como B não deve criar movimentação em produto de A."""
    with app.test_client() as client:
        uid_a, uid_b = _make_user(), _make_user()
        pid_a = estoque_repository.insert_produto(uid_a, "Produto de A2", "ml", "medicamento", 0)
        estoque_repository.insert_movimentacao(uid_a, pid_a, 'entrada', 100.0, None, None, "2024-01-01")
        _login(client, uid_b)

        client.post(f"/estoque/{pid_a}/saida", data={
            "quantidade": "50", "data_mov": "2024-06-01",
        }, follow_redirects=True)

        assert estoque_repository.get_saldo_atual(pid_a, uid_a) == pytest.approx(100.0)
        _purge(uid_a)
        _purge(uid_b)


def test_detalhe_estoque_produto_alheio_nao_exibe_dados(app):
    """GET /estoque/<id_de_A> como B não deve expor o nome do produto de A."""
    with app.test_client() as client:
        uid_a, uid_b = _make_user(), _make_user()
        pid_a = estoque_repository.insert_produto(uid_a, "Produto Sigiloso A", "ml", "medicamento", 0)
        _login(client, uid_b)

        r = client.get(f"/estoque/{pid_a}", follow_redirects=True)
        assert b"Produto Sigiloso A" not in r.data
        _purge(uid_a)
        _purge(uid_b)


def test_importar_csv_brinco_duplicado(app):
    """Brinco já existente vai para coluna de erros sem travar a importação."""
    with app.test_client() as client:
        import io as _io
        uid = _make_user()
        _login(client, uid)

        # Cria o animal antecipadamente
        conn = dbc.get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO animais (brinco,sexo,data_compra,preco_compra,user_id) "
            "VALUES ('DUP-001','M','2025-01-01',1000,%s)", (uid,)
        )
        conn.commit(); cur.close(); conn.close()

        csv_content = (
            "brinco,sexo,data_compra,peso_kg,valor_arroba\n"
            "DUP-001,M,2026-01-10,300,185.00\n"   # duplicado
            "DUP-002,F,2026-01-10,250,175.00\n"   # novo
        ).encode('utf-8')
        r = client.post("/importar-csv", data={
            "arquivo": (_io.BytesIO(csv_content), "animais.csv"),
        }, content_type='multipart/form-data', follow_redirects=True)
        assert r.status_code == 200
        assert b'1' in r.data   # 1 inserido (DUP-002)
        _purge(uid)
