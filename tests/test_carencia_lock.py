"""SGG+ PR 1 — carência sanitária: a trava na venda e o registro do override.

O limite que importa é `dias_restantes = 0`: a data de liberação é o primeiro dia
em que o animal PODE ir ao abate, então no dia da liberação a venda passa.
"""
import itertools
from datetime import date, timedelta

import pytest
from werkzeug.security import generate_password_hash

from repositories import animal_repository, sanitario_repository
from tests.dbcompat import connect
from utils.carencia import dias_carencia_sugerido

_seq = itertools.count(9000)


def _n():
    return next(_seq)


def _make_user():
    conn = connect(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
        (f"car_{_n()}", generate_password_hash("x")),
    )
    uid = cur.lastrowid
    conn.commit(); cur.close(); conn.close()
    return uid


def _make_animal(user_id, brinco=None):
    brinco = brinco or f"CAR{_n()}"
    conn = connect(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id)"
        " VALUES (%s, 'M', '2024-01-01', 1000, %s)",
        (brinco, user_id),
    )
    aid = cur.lastrowid
    cur.execute(
        "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, '2024-01-01', 400)",
        (aid,),
    )
    conn.commit(); cur.close(); conn.close()
    return aid, brinco


def _medicar(animal_id, dias_carencia, data_aplicacao=None):
    """Insere direto: o alvo é posicionar a data de liberação em relação a hoje."""
    data_aplicacao = data_aplicacao or date.today()
    conn = connect(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO medicacoes (animal_id, data_aplicacao, nome_medicamento, custo, dias_carencia)"
        " VALUES (%s, %s, 'Ivermectina', 10, %s)",
        (animal_id, data_aplicacao, dias_carencia),
    )
    mid = cur.lastrowid
    conn.commit(); cur.close(); conn.close()
    return mid


def _overrides(animal_id):
    conn = connect(); cur = conn.cursor()
    cur.execute(
        "SELECT medicacao_id, autorizado_por, data_liberacao FROM vendas_com_carencia "
        "WHERE animal_id = %s ORDER BY id",
        (animal_id,),
    )
    linhas = cur.fetchall()
    cur.close(); conn.close()
    return linhas


def _purge(user_id):
    conn = connect(); cur = conn.cursor()
    cur.execute("SET session_replication_role = 'replica'")
    for sql in [
        "DELETE FROM vendas_com_carencia v USING animais a "
        " WHERE v.animal_id = a.id AND a.user_id = %s",
        "DELETE FROM vendas_com_carencia WHERE autorizado_por = %s",
        "DELETE FROM medicacoes m USING animais a WHERE m.animal_id = a.id AND a.user_id = %s",
        "DELETE FROM pesagens p USING animais a WHERE p.animal_id = a.id AND a.user_id = %s",
        "DELETE FROM animais WHERE user_id = %s",
        "DELETE FROM usuarios WHERE id = %s",
    ]:
        cur.execute(sql, (user_id,))
    cur.execute("SET session_replication_role = 'origin'")
    conn.commit(); cur.close(); conn.close()


def _login(client, uid):
    conn = connect(); cur = conn.cursor()
    cur.execute("SELECT username FROM usuarios WHERE id = %s", (uid,))
    username = cur.fetchone()[0]
    cur.close(); conn.close()
    client.post("/login", data={"username": username, "password": "x"}, follow_redirects=True)


def _vendido(animal_id):
    conn = connect(); cur = conn.cursor()
    cur.execute("SELECT data_venda FROM animais WHERE id = %s", (animal_id,))
    dt = cur.fetchone()[0]
    cur.close(); conn.close()
    return dt is not None


@pytest.fixture
def um(app):
    uid = _make_user()
    yield uid
    _purge(uid)


def _form(**extra):
    base = {"data_venda": date.today().isoformat(), "peso_venda": "500",
            "valor_arroba": "300"}
    base.update(extra)
    return base


# ---- a trava ----

def test_venda_dentro_da_carencia_da_400(client, um):
    aid, brinco = _make_animal(um)
    _medicar(aid, 35)
    _login(client, um)

    r = client.post(f"/vender/{aid}", data=_form())
    assert r.status_code == 400
    corpo = r.get_data(as_text=True)
    assert brinco in corpo
    assert (date.today() + timedelta(days=35)).strftime("%d/%m/%Y") in corpo
    assert not _vendido(aid)
    assert _overrides(aid) == []


def test_override_vende_e_grava_auditoria(client, um):
    aid, _ = _make_animal(um)
    mid = _medicar(aid, 35)
    _login(client, um)

    r = client.post(f"/vender/{aid}", data=_form(confirmar_carencia="1"))
    assert r.status_code == 302
    assert _vendido(aid)
    linhas = _overrides(aid)
    assert len(linhas) == 1
    assert linhas[0][0] == mid
    assert linhas[0][1] == um
    assert linhas[0][2] == date.today() + timedelta(days=35)


def test_no_dia_da_liberacao_a_venda_passa(client, um):
    """dias_restantes = 0 é o limite: liberado, sem override e sem auditoria."""
    aid, _ = _make_animal(um)
    _medicar(aid, 35, data_aplicacao=date.today() - timedelta(days=35))
    _login(client, um)

    assert sanitario_repository.get_carencias_ativas(um, animal_ids=[aid]) == []
    r = client.post(f"/vender/{aid}", data=_form())
    assert r.status_code == 302
    assert _vendido(aid)
    assert _overrides(aid) == []


def test_vespera_da_liberacao_ainda_trava(client, um):
    aid, _ = _make_animal(um)
    _medicar(aid, 35, data_aplicacao=date.today() - timedelta(days=34))
    _login(client, um)

    carencias = sanitario_repository.get_carencias_ativas(um, animal_ids=[aid])
    assert len(carencias) == 1
    assert carencias[0][7] == 1          # dias_restantes
    assert client.post(f"/vender/{aid}", data=_form()).status_code == 400


def test_carencia_zero_nao_trava(client, um):
    aid, _ = _make_animal(um)
    _medicar(aid, 0)
    _login(client, um)

    assert sanitario_repository.get_carencias_ativas(um, animal_ids=[aid]) == []
    assert client.post(f"/vender/{aid}", data=_form()).status_code == 302


def test_medicacao_excluida_nao_trava(client, um):
    aid, _ = _make_animal(um)
    mid = _medicar(aid, 35)
    conn = connect(); cur = conn.cursor()
    cur.execute("UPDATE medicacoes SET deleted_at = now() WHERE id = %s", (mid,))
    conn.commit(); cur.close(); conn.close()
    _login(client, um)

    assert client.post(f"/vender/{aid}", data=_form()).status_code == 302


# ---- venda em lote ----

def test_venda_lote_trava_e_nao_vende_ninguem(client, um):
    livre, _ = _make_animal(um)
    preso, brinco_preso = _make_animal(um)
    _medicar(preso, 35)
    _login(client, um)

    r = client.post("/venda-lote", data={
        "data_venda": date.today().isoformat(), "valor_arroba": "300",
        "animal_ids[]": [str(livre), str(preso)],
        "pesos_venda[]": ["500", "480"],
    })
    assert r.status_code == 400
    assert brinco_preso in r.get_data(as_text=True)
    assert not _vendido(livre), "a trava vale para o lote inteiro, não só o animal preso"
    assert not _vendido(preso)


def test_venda_lote_com_override_grava_so_quem_estava_preso(client, um):
    livre, _ = _make_animal(um)
    preso, _ = _make_animal(um)
    mid = _medicar(preso, 35)
    _login(client, um)

    r = client.post("/venda-lote", data={
        "data_venda": date.today().isoformat(), "valor_arroba": "300",
        "animal_ids[]": [str(livre), str(preso)],
        "pesos_venda[]": ["500", "480"],
        "confirmar_carencia": "1",
    })
    assert r.status_code == 302
    assert _vendido(livre) and _vendido(preso)
    assert _overrides(livre) == []
    assert [l[0] for l in _overrides(preso)] == [mid]


# ---- isolamento por fazenda ----

def test_carencia_de_outra_fazenda_nao_aparece(app):
    a, b = _make_user(), _make_user()
    try:
        aid_a, _ = _make_animal(a)
        _medicar(aid_a, 35)
        assert len(sanitario_repository.get_carencias_ativas(a)) == 1
        assert sanitario_repository.get_carencias_ativas(b) == []
        # mesmo passando o id do animal alheio, a view filtra por user_id
        assert sanitario_repository.get_carencias_ativas(b, animal_ids=[aid_a]) == []
    finally:
        _purge(a); _purge(b)


def test_animal_vendido_sai_da_view(app):
    uid = _make_user()
    try:
        aid, _ = _make_animal(uid)
        _medicar(aid, 35)
        conn = connect(); cur = conn.cursor()
        cur.execute("UPDATE animais SET data_venda = CURRENT_DATE WHERE id = %s", (aid,))
        conn.commit(); cur.close(); conn.close()
        assert sanitario_repository.get_carencias_ativas(uid) == []
    finally:
        _purge(uid)


def test_lista_vazia_de_ids_nao_consulta(app):
    assert sanitario_repository.get_carencias_ativas(1, animal_ids=[]) == []


# ---- o dia-a-dia da aplicação ----

def test_registrar_medicacao_grava_carencia(app):
    uid = _make_user()
    try:
        aid, _ = _make_animal(uid)
        animal_repository.registrar_medicacao(
            aid, uid, date.today().isoformat(), 'Ivermectina 1%', 10, '', dias_carencia=35)
        meds = animal_repository.get_medicacoes_by_animal(aid)
        assert meds[0][6] == 35
        assert meds[0][7] == date.today() + timedelta(days=35)
    finally:
        _purge(uid)


def test_formulario_em_branco_cai_na_sugestao_do_produto(client, app):
    uid = _make_user()
    try:
        aid, _ = _make_animal(uid)
        _login(client, uid)
        r = client.post(f"/medicar/{aid}", data={
            "data_aplicacao": date.today().isoformat(),
            "nome": "Ivermectina 1% 10ml", "custo": "10", "obs": "",
        })
        assert r.status_code == 302
        assert animal_repository.get_medicacoes_by_animal(aid)[0][6] == 35
    finally:
        _purge(uid)


def test_zero_explicito_vence_a_sugestao(client, app):
    uid = _make_user()
    try:
        aid, _ = _make_animal(uid)
        _login(client, uid)
        r = client.post(f"/medicar/{aid}", data={
            "data_aplicacao": date.today().isoformat(),
            "nome": "Ivermectina", "custo": "10", "obs": "", "dias_carencia": "0",
        })
        assert r.status_code == 302
        assert animal_repository.get_medicacoes_by_animal(aid)[0][6] == 0
    finally:
        _purge(uid)


@pytest.mark.parametrize("nome,esperado", [
    ("Ivermectina 1% 10ml", 35),
    ("ivomec (ivermectina)", 35),
    ("DORAMECTINA", 42),
    ("Vacina Febre Aftosa", 0),
    ("Vitamina ADE", 0),
    ("", 0),
    (None, 0),
])
def test_sugestao_por_nome(nome, esperado):
    assert dias_carencia_sugerido(nome) == esperado


# ---- as telas que a carência passou a alimentar ----

def test_telas_tocadas_renderizam(client, app):
    uid = _make_user()
    try:
        aid, brinco = _make_animal(uid)
        _medicar(aid, 35)
        _login(client, uid)

        r = client.get('/inicio')
        assert r.status_code == 200
        corpo = r.get_data(as_text=True)
        assert 'Animais em carência sanitária' in corpo
        assert brinco in corpo

        r = client.get(f'/animal/{aid}')
        assert r.status_code == 200
        assert '35 d — libera' in r.get_data(as_text=True)

        for url in ('/vacinacao-coletiva', '/venda-lote', f'/vender/{aid}'):
            assert client.get(url).status_code == 200, url
    finally:
        _purge(uid)


def test_vacinacao_coletiva_grava_carencia_sugerida(client, app):
    uid = _make_user()
    try:
        aid, _ = _make_animal(uid)
        _login(client, uid)
        r = client.post('/vacinacao-coletiva', data={
            'animais_ids': [str(aid)], 'data_aplicacao': date.today().isoformat(),
            'nome': 'Doramectina', 'custo': '5', 'obs': '',
        })
        assert r.status_code == 302
        assert animal_repository.get_medicacoes_by_animal(aid)[0][6] == 42
    finally:
        _purge(uid)


def test_lotes_sem_pesagem_entra_no_inicio(client, app):
    uid = _make_user()
    try:
        conn = connect(); cur = conn.cursor()
        cur.execute(
            "INSERT INTO lotes (user_id, codigo_lote, data_aquisicao) "
            "VALUES (%s, %s, CURRENT_DATE - 100)",
            (uid, f"L{_n()}"),
        )
        lote_id = cur.lastrowid
        conn.commit(); cur.close(); conn.close()

        aid, _ = _make_animal(uid)   # última pesagem em 2024-01-01
        conn = connect(); cur = conn.cursor()
        cur.execute("UPDATE animais SET lote_id = %s WHERE id = %s", (lote_id, aid))
        conn.commit(); cur.close(); conn.close()

        paradas = animal_repository.get_lotes_sem_pesagem(uid, dias=45)
        assert [p[0] for p in paradas] == [lote_id]
        assert paradas[0][2] == 1                       # cabeças

        # pesada hoje, sai da lista
        conn = connect(); cur = conn.cursor()
        cur.execute(
            "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, CURRENT_DATE, 450)",
            (aid,),
        )
        conn.commit(); cur.close(); conn.close()
        assert animal_repository.get_lotes_sem_pesagem(uid, dias=45) == []

        _login(client, uid)
        assert client.get('/inicio').status_code == 200
    finally:
        conn = connect(); cur = conn.cursor()
        cur.execute("UPDATE animais SET lote_id = NULL WHERE user_id = %s", (uid,))
        cur.execute("DELETE FROM lotes WHERE user_id = %s", (uid,))
        conn.commit(); cur.close(); conn.close()
        _purge(uid)
