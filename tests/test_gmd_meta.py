"""
Sprint 6 — GMD Meta Configurável.
Repositório: configuracao_repository (coluna gmd_meta) / animal_repository.get_animais_abaixo_gmd_meta
Rota: /configuracoes (form) e /animais/<id>/progenie (consumo do valor)
"""
import pytest
import itertools
from werkzeug.security import generate_password_hash
import db_config as dbc
from repositories import animal_repository, configuracao_repository

_seq = itertools.count(10000)


def _n():
    return next(_seq)


def _make_user():
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
        (f"gm_{_n()}", generate_password_hash("x")),
    )
    uid = cur.lastrowid
    conn.commit(); cur.close(); conn.close()
    return uid


def _make_animal_com_gmd(user_id, gmd_alvo, brinco=None):
    """Cria animal com 2 pesagens que produzem exatamente o GMD desejado em 10 dias."""
    brinco = brinco or f"GM{_n()}"
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id)"
        " VALUES (%s, 'M', '2024-01-01', 1000, %s)",
        (brinco, user_id),
    )
    aid = cur.lastrowid
    cur.execute(
        "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, '2024-01-01', 300)", (aid,)
    )
    peso_final = 300 + (gmd_alvo * 10)
    cur.execute(
        "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, '2024-01-11', %s)",
        (aid, peso_final),
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
    client.post("/login", data={"username": username, "password": "x"}, follow_redirects=True)


@pytest.fixture
def um(app):
    uid = _make_user()
    yield uid
    _purge(uid)


# ── repositório ──────────────────────────────────────────────────────────────

def test_configuracao_default_gmd_meta_e_0_800(um):
    configuracao_repository.upsert_configuracao(um, "Fazenda X", "Cidade/UF", 100)
    res = configuracao_repository.get_configuracao(um)
    assert float(res[3]) == 0.800


def test_configuracao_persiste_gmd_meta_customizado(um):
    configuracao_repository.upsert_configuracao(um, "Fazenda X", "Cidade/UF", 100, gmd_meta=1.200)
    res = configuracao_repository.get_configuracao(um)
    assert float(res[3]) == 1.200


def test_get_animais_abaixo_gmd_meta_filtra_pelo_limiar(um):
    # meta = 1.000 -> limiar = 0.750
    abaixo = _make_animal_com_gmd(um, gmd_alvo=0.5, brinco='ABAIXO')
    acima = _make_animal_com_gmd(um, gmd_alvo=1.1, brinco='ACIMA')

    resultado = animal_repository.get_animais_abaixo_gmd_meta(um, 1.000)
    ids = [r[0] for r in resultado]

    assert abaixo in ids
    assert acima not in ids


# ── rota ─────────────────────────────────────────────────────────────────────

def test_rota_configuracoes_post_salva_gmd_meta(app):
    uid = _make_user()
    try:
        with app.test_client() as client:
            _login(client, uid)
            r = client.post("/configuracoes", data={
                'nome_fazenda': 'Fazenda Teste',
                'cidade_estado': 'Cidade/UF',
                'area_total': '50',
                'gmd_meta': '1.200',
            }, follow_redirects=True)
            assert r.status_code == 200

        res = configuracao_repository.get_configuracao(uid)
        assert float(res[3]) == 1.200
    finally:
        _purge(uid)


def test_rota_detalhes_reflete_gmd_meta_customizada(app):
    """GMD 0.9 é 'Ótimo' com meta padrão (0.8) mas 'Baixo' com meta customizada (1.5)."""
    uid = _make_user()
    try:
        configuracao_repository.upsert_configuracao(uid, "Fazenda", "Cidade/UF", 10, gmd_meta=1.500)
        animal_id = _make_animal_com_gmd(uid, gmd_alvo=0.9, brinco='DET-GM')

        with app.test_client() as client:
            _login(client, uid)
            r = client.get(f"/animal/{animal_id}")
            assert r.status_code == 200
            assert b"Ganho abaixo do ideal" in r.data
            assert b"Desempenho elevado" not in r.data
    finally:
        _purge(uid)


def test_rota_progenie_exibe_gmd_meta_customizada(app):
    uid = _make_user()
    try:
        configuracao_repository.upsert_configuracao(uid, "Fazenda", "Cidade/UF", 10, gmd_meta=1.200)
        touro_id = _make_animal_com_gmd(uid, gmd_alvo=0.7, brinco='TOURO-GM')

        # Gráfico de referência só renderiza com >= 2 filhos com GMD calculado
        conn = dbc.get_db_connection()
        cur = conn.cursor()
        for i in range(2):
            filho_id = _make_animal_com_gmd(uid, gmd_alvo=0.6, brinco=f'FILHO{i}-{_n()}')
            cur.execute("UPDATE animais SET pai_id = %s WHERE id = %s", (touro_id, filho_id))
        conn.commit(); cur.close(); conn.close()

        with app.test_client() as client:
            _login(client, uid)
            r = client.get(f"/animais/{touro_id}/progenie")
            assert r.status_code == 200
            assert b"1.200" in r.data
    finally:
        _purge(uid)
