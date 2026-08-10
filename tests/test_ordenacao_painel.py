"""
Ordenação do painel por peso e GMD.
Repositório: animal_repository.get_animais_paginados (parâmetro ordem)
Rota: GET /painel?ord=gmd_desc|gmd_asc|peso_desc|peso_asc|brinco
"""
import pytest
import itertools
from werkzeug.security import generate_password_hash
import db_config as dbc
from repositories import animal_repository

_seq = itertools.count(21000)


def _n():
    return next(_seq)


def _make_user():
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
        (f"ord_{_n()}", generate_password_hash("x")),
    )
    uid = cur.lastrowid
    conn.commit(); cur.close(); conn.close()
    return uid


def _make_animal(user_id, brinco):
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


@pytest.fixture
def trio(um):
    """Três animais que separam peso de GMD:

    RAPIDO  200 → 320 kg em 60 dias → GMD 2.0, peso final 320
    LENTO   200 → 260 kg em 60 dias → GMD 1.0, peso final 260
    PESADO  uma pesagem só de 400 kg → GMD NULL, mas o MAIOR peso do lote

    PESADO é o que importa: sem ele, um bug que confunda "sem GMD" com "GMD
    baixo" passaria despercebido, porque peso e GMD andariam juntos.
    """
    rapido = _make_animal(um, f"RAPIDO{_n()}")
    lento  = _make_animal(um, f"LENTO{_n()}")
    pesado = _make_animal(um, f"PESADO{_n()}")
    _add_pesagem(rapido, '2024-01-01', 200); _add_pesagem(rapido, '2024-03-01', 320)
    _add_pesagem(lento,  '2024-01-01', 200); _add_pesagem(lento,  '2024-03-01', 260)
    _add_pesagem(pesado, '2024-01-01', 400)
    return um, rapido, lento, pesado


def _ids(um, ordem):
    return [a[0] for a in animal_repository.get_animais_paginados(um, 20, 0, ordem=ordem)]


# ── repositório: ordem ───────────────────────────────────────────────────────

def test_gmd_desc_traz_o_melhor_primeiro(trio):
    um, rapido, lento, pesado = trio
    assert _ids(um, 'gmd_desc') == [rapido, lento, pesado]


def test_gmd_asc_traz_o_pior_medido_primeiro_e_o_sem_gmd_por_ultimo(trio):
    """O ponto do `g.gmd IS NULL` no ORDER BY: quem pede "menor GMD" quer o pior
    boi medido. No ASC puro do MySQL o NULL viria primeiro e a tela abriria com
    animais de uma pesagem só."""
    um, rapido, lento, pesado = trio
    assert _ids(um, 'gmd_asc') == [lento, rapido, pesado]


def test_peso_desc_ordena_pelo_ultimo_peso(trio):
    um, rapido, lento, pesado = trio
    assert _ids(um, 'peso_desc') == [pesado, rapido, lento]


def test_peso_asc_ordena_pelo_ultimo_peso(trio):
    um, rapido, lento, pesado = trio
    assert _ids(um, 'peso_asc') == [lento, rapido, pesado]


def test_ordem_padrao_continua_por_brinco(trio):
    um, _, _, _ = trio
    brincos = [a[1] for a in animal_repository.get_animais_paginados(um, 20, 0)]
    assert brincos == sorted(brincos, key=lambda b: (len(b), b))


# ── repositório: colunas peso/GMD ────────────────────────────────────────────

def test_ordem_por_brinco_nao_calcula_gmd(trio):
    """As colunas 8 e 9 vêm vazias no caminho barato — o painel continua
    buscando os valores por /api/animais/gmd-lote."""
    um, _, _, _ = trio
    assert not animal_repository.ordenacao_traz_gmd('brinco')
    for animal in animal_repository.get_animais_paginados(um, 20, 0):
        assert animal[8] is None and animal[9] is None


def test_ordem_por_gmd_ja_devolve_peso_e_gmd(trio):
    um, rapido, _, pesado = trio
    assert animal_repository.ordenacao_traz_gmd('gmd_desc')
    linhas = {a[0]: a for a in animal_repository.get_animais_paginados(um, 20, 0, ordem='gmd_desc')}

    assert float(linhas[rapido][8]) == 320
    assert float(linhas[rapido][9]) == 2.0
    # uma pesagem só: tem peso, não tem GMD
    assert float(linhas[pesado][8]) == 400
    assert linhas[pesado][9] is None


# ── repositório: robustez ────────────────────────────────────────────────────

@pytest.mark.parametrize("lixo", [
    "", "gmd", "brinco; DROP TABLE animais", "a.brinco DESC", None,
])
def test_ordenacao_desconhecida_cai_no_padrao(trio, lixo):
    """Só a chave vem de fora; o SQL é literal. Qualquer coisa fora da whitelist
    vira a ordenação padrão em vez de chegar ao banco."""
    um, _, _, _ = trio
    assert animal_repository.normalizar_ordenacao(lixo) == 'brinco'
    assert _ids(um, lixo) == _ids(um, 'brinco')


def test_paginacao_por_gmd_nao_repete_nem_perde_animal(um):
    """Empate em massa (todos sem GMD) é onde falta de desempate estável dói:
    sem o `a.id` no fim do ORDER BY, o mesmo animal aparece em duas páginas."""
    for i in range(6):
        _make_animal(um, f"EMP{i}{_n()}")

    p1 = [a[0] for a in animal_repository.get_animais_paginados(um, 3, 0, ordem='gmd_desc')]
    p2 = [a[0] for a in animal_repository.get_animais_paginados(um, 3, 3, ordem='gmd_desc')]

    assert len(set(p1 + p2)) == 6


def test_ordenacao_por_gmd_respeita_o_filtro(trio):
    um, rapido, lento, pesado = trio
    ids = [a[0] for a in animal_repository.get_animais_paginados(
        um, 20, 0, termo='RAPIDO', ordem='gmd_desc')]
    assert ids == [rapido]


def test_ordenacao_por_gmd_nao_vaza_animal_de_outro_usuario(trio):
    """A CTE de GMD é um caminho de query novo — o filtro por user_id precisa
    valer nele também."""
    um, _, _, _ = trio
    outro = _make_user()
    try:
        alheio = _make_animal(outro, f"ALHEIO{_n()}")
        _add_pesagem(alheio, '2024-01-01', 100)
        _add_pesagem(alheio, '2024-03-01', 900)  # GMD altíssimo: seria o 1º da lista

        assert alheio not in _ids(um, 'gmd_desc')
        assert alheio not in _ids(um, 'peso_desc')
    finally:
        _purge(outro)


# ── rota ─────────────────────────────────────────────────────────────────────

def test_rota_painel_ordena_por_gmd(app, trio):
    um, rapido, lento, pesado = trio
    with app.test_client() as client:
        _login(client, um)
        html = client.get('/painel?ord=gmd_desc').get_data(as_text=True)

    assert html.index('RAPIDO') < html.index('LENTO') < html.index('PESADO')


def test_rota_painel_embute_peso_e_gmd_ao_ordenar(app, trio):
    """Ordenando por GMD a página já traz os números, e o front não repete a
    chamada a /api/animais/gmd-lote."""
    um, _, _, _ = trio
    with app.test_client() as client:
        _login(client, um)
        html = client.get('/painel?ord=gmd_desc').get_data(as_text=True)

    assert 'data-gmd-embutido="1"' in html
    assert 'data-gmd="2.000"' in html


def test_rota_painel_sem_ordenacao_nao_embute(app, trio):
    um, _, _, _ = trio
    with app.test_client() as client:
        _login(client, um)
        html = client.get('/painel').get_data(as_text=True)

    # a marca é o atributo no <tbody>; a string crua também aparece no seletor
    # do script inline, por isso a asserção casa o atributo com valor
    assert 'data-gmd-embutido="1"' not in html
    assert 'data-gmd=' not in html


def test_rota_painel_ordenacao_invalida_nao_quebra(app, trio):
    um, _, _, _ = trio
    with app.test_client() as client:
        _login(client, um)
        r = client.get('/painel?ord=%27%20OR%201=1--')

    assert r.status_code == 200


def test_rota_painel_preserva_ordenacao_nos_links_de_filtro(app, trio):
    """Trocar de filtro não pode derrubar a ordem escolhida (nem vice-versa)."""
    um, _, _, _ = trio
    with app.test_client() as client:
        _login(client, um)
        html = client.get('/painel?ord=peso_desc&status=ativos').get_data(as_text=True)

    assert 'ord=peso_desc' in html
    assert 'status=ativos' in html
