"""
Testes de cobertura para endpoints de dashboard/gráficos e cotações
(routes/api.py) que não tinham nenhum teste direto de rota.
"""
import itertools
import pytest
from werkzeug.security import generate_password_hash
import db_config as dbc
from repositories import configuracao_repository

_seq = itertools.count(13000)


def _n():
    return next(_seq)


def _make_user():
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
        (f"dash_{_n()}", generate_password_hash("x")),
    )
    uid = cur.lastrowid
    conn.commit(); cur.close(); conn.close()
    return uid


def _purge(user_id):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    for sql in [
        "DELETE p FROM pesagens p JOIN animais a ON p.animal_id = a.id WHERE a.user_id = %s",
        "DELETE FROM animais WHERE user_id = %s",
        "DELETE FROM custos_operacionais WHERE user_id = %s",
        "DELETE FROM configuracoes WHERE user_id = %s",
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


@pytest.fixture
def um(app):
    uid = _make_user()
    yield uid
    _purge(uid)


# ── /graficos (página) ───────────────────────────────────────────────────────

def test_graficos_page_requer_login(app):
    with app.test_client() as client:
        r = client.get('/graficos')
        assert r.status_code in (302, 401)


def test_graficos_page_logado_retorna_200(app, um):
    with app.test_client() as client:
        _login(client, um)
        r = client.get('/graficos')
        assert r.status_code == 200


# ── /api/graficos/peso ───────────────────────────────────────────────────────

def test_graficos_peso_sem_animais_retorna_zeros(app, um):
    with app.test_client() as client:
        _login(client, um)
        r = client.get('/api/graficos/peso')
        assert r.status_code == 200
        data = r.get_json()
        assert set(data.keys()) == {'Menos de 10@', '10@ a 15@', '15@ a 20@', 'Mais de 20@'}
        assert sum(data.values()) == 0


def test_graficos_peso_classifica_por_arroba(app, um):
    with app.test_client() as client:
        _login(client, um)
        conn = dbc.get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id) "
            "VALUES ('DASH-PESO-01','M','2024-01-01',1000,%s)", (um,)
        )
        aid = cur.lastrowid
        # 450kg / 30 = 15@ -> cai em "15@ a 20@"
        cur.execute(
            "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, '2024-06-01', 450)",
            (aid,)
        )
        conn.commit(); cur.close(); conn.close()

        r = client.get('/api/graficos/peso')
        assert r.status_code == 200
        data = r.get_json()
        assert data['15@ a 20@'] == 1


# ── /api/animais/gmd-lote ────────────────────────────────────────────────────

def test_gmd_lote_sem_ids_retorna_vazio(app, um):
    with app.test_client() as client:
        _login(client, um)
        r = client.get('/api/animais/gmd-lote')
        assert r.status_code == 200
        assert r.get_json() == {}


def test_gmd_lote_ids_invalidos_retorna_400(app, um):
    with app.test_client() as client:
        _login(client, um)
        r = client.get('/api/animais/gmd-lote?ids=abc,def')
        assert r.status_code == 400


def test_gmd_lote_mais_de_50_ids_retorna_400(app, um):
    with app.test_client() as client:
        _login(client, um)
        ids = ','.join(str(i) for i in range(1, 52))
        r = client.get(f'/api/animais/gmd-lote?ids={ids}')
        assert r.status_code == 400


def test_gmd_lote_ids_validos_retorna_dados_do_proprio_usuario(app, um):
    with app.test_client() as client:
        _login(client, um)
        conn = dbc.get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id) "
            "VALUES ('DASH-GMD-01','M','2024-01-01',1000,%s)", (um,)
        )
        aid = cur.lastrowid
        cur.execute(
            "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, '2024-01-01', 300), "
            "(%s, '2024-02-01', 330)",
            (aid, aid)
        )
        conn.commit(); cur.close(); conn.close()

        r = client.get(f'/api/animais/gmd-lote?ids={aid}')
        assert r.status_code == 200
        data = r.get_json()
        assert str(aid) in data


def test_gmd_lote_ignora_animal_de_outro_usuario(app):
    with app.test_client() as client:
        uid_a, uid_b = _make_user(), _make_user()
        conn = dbc.get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id) "
            "VALUES ('DASH-GMD-ALHEIO','M','2024-01-01',1000,%s)", (uid_a,)
        )
        aid_a = cur.lastrowid
        conn.commit(); cur.close(); conn.close()

        _login(client, uid_b)
        r = client.get(f'/api/animais/gmd-lote?ids={aid_a}')
        assert r.status_code == 200
        assert r.get_json() == {}
        _purge(uid_a)
        _purge(uid_b)


# ── /api/financeiro/custos ───────────────────────────────────────────────────

def test_custos_por_ano_retorna_lista_json(app, um):
    with app.test_client() as client:
        _login(client, um)
        conn = dbc.get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO custos_operacionais (user_id, categoria, tipo_custo, valor, data_custo, descricao) "
            "VALUES (%s, 'Fixo', 'Salário', 500.0, '2024-06-01', 'Teste API')", (um,)
        )
        conn.commit(); cur.close(); conn.close()

        r = client.get('/api/financeiro/custos?ano=2024')
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data, list)
        # 'categoria' é o centro de custo (Fixo/Variavel); 'descricao' aqui carrega o
        # tipo_custo (ex. Salário) — ver routes/api.py::custos_por_ano.
        assert any(item['categoria'] == 'Fixo' and item['descricao'] == 'Salário'
                   and item['valor'] == 500.0 for item in data)


# ── /api/v1/alertas/gmd ──────────────────────────────────────────────────────

def test_alerta_gmd_sem_animais_retorna_estrutura_vazia(app, um):
    with app.test_client() as client:
        _login(client, um)
        r = client.get('/api/v1/alertas/gmd')
        assert r.status_code == 200
        data = r.get_json()
        assert data['total'] == 0
        assert data['animais'] == []
        assert 'gmd_media_rebanho' in data


# ── /cotacoes-regionais e /cotacoes-brasil ───────────────────────────────────

def test_cotacoes_regionais_sem_localizacao_retorna_404(app, um):
    with app.test_client() as client:
        _login(client, um)
        r = client.get('/cotacoes-regionais')
        assert r.status_code == 404
        assert 'erro' in r.get_json()


def test_cotacoes_regionais_com_localizacao_retorna_uf(app, um):
    with app.test_client() as client:
        _login(client, um)
        configuracao_repository.upsert_configuracao(um, 'Fazenda Teste', 'Ribeirão Preto-SP', 100.0)
        r = client.get('/cotacoes-regionais')
        assert r.status_code == 200
        data = r.get_json()
        assert data['uf'] == 'SP'
        assert 'boi' in data and 'novilha' in data


def test_cotacoes_brasil_retorna_estrutura(app, um):
    with app.test_client() as client:
        _login(client, um)
        r = client.get('/cotacoes-brasil')
        assert r.status_code == 200
        data = r.get_json()
        assert 'boi' in data and 'novilha' in data


def test_fetch_cotacoes_descarta_json_nao_lista(app, monkeypatch):
    """Issue #48 — feed externo que retorne JSON válido mas não-lista
    (ex.: {}) não pode vazar para o front; _get devolve [] nesse caso."""
    from routes import api as api_mod

    class _FakeResp:
        status_code = 200
        def json(self):
            return {"erro": "<script>alert(1)</script>"}

    monkeypatch.setattr(api_mod.requests, "get", lambda *a, **k: _FakeResp())
    api_mod._cotacoes_cache['ts'] = 0  # invalida cache p/ forçar fetch
    boi, novilha = api_mod._fetch_cotacoes_github()
    assert boi == [] and novilha == []
