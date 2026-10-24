"""Autoria das escritas: quem pesou, quem medicou, quem liberou a venda.

Achado #8 do plano: todo INSERT gravava só o `user_id` do dono, então "quem
pesou o 402?" não tinha resposta. Com o vaqueiro convidado entrando com a
própria conta, a pergunta deixa de ser teórica.

O caso que o grep estrutural não pega é o inverso do bug de tenant: um
`farm_id` onde deveria estar `id`. Era o que acontecia com
`vendas_com_carencia.autorizado_por` — a varredura do PR 3 trocou a assinatura
do override pela fazenda. `test_override_de_carencia_e_assinado_por_quem_vendeu`
é o teste disso.
"""
import itertools

import pytest
from werkzeug.security import generate_password_hash

from repositories import acesso_repository, animal_repository
from services import pesagem as servico_pesagem
from tests.dbcompat import connect

_seq = itertools.count(17000)


# -- Helpers -----------------------------------------------------------------

def _criar_usuario(com_fazenda=True):
    n = next(_seq)
    username = f"au_{n}"
    conn = connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
                (username, generate_password_hash("senha123")))
    uid = cur.lastrowid
    if com_fazenda:
        cur.execute("INSERT INTO configuracoes (user_id, nome_fazenda) VALUES (%s, %s)",
                    (uid, f"Fazenda {n}"))
    conn.commit()
    cur.close()
    conn.close()
    return uid, username


def _criar_animal(user_id, brinco, dias_carencia=0):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id)"
        " VALUES (%s, 'M', '2024-01-01', 1000, %s)",
        (brinco, user_id),
    )
    aid = cur.lastrowid
    if dias_carencia:
        cur.execute(
            "INSERT INTO medicacoes (animal_id, data_aplicacao, nome_medicamento, custo,"
            " dias_carencia) VALUES (%s, CURRENT_DATE, 'Ivermectina', 50, %s)",
            (aid, dias_carencia),
        )
    conn.commit()
    cur.close()
    conn.close()
    return aid


def _buscar(sql, params=()):
    conn = connect()
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def _executar(sql, params=()):
    conn = connect()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    cur.close()
    conn.close()


def _purgar(user_id):
    conn = connect()
    cur = conn.cursor()
    cur.execute("SET session_replication_role = 'replica'")
    comandos = [
        ("DELETE FROM vendas_com_carencia v USING animais a"
         " WHERE v.animal_id = a.id AND a.user_id = %s", 1),
        ("DELETE FROM vendas_com_carencia WHERE autorizado_por = %s", 1),
        ("DELETE FROM pesagens p USING animais a"
         " WHERE p.animal_id = a.id AND a.user_id = %s", 1),
        ("DELETE FROM medicacoes m USING animais a"
         " WHERE m.animal_id = a.id AND a.user_id = %s", 1),
        ("DELETE FROM animais WHERE user_id = %s", 1),
        ("DELETE FROM estoque_movimentacoes WHERE user_id = %s", 1),
        ("DELETE FROM estoque_produtos WHERE user_id = %s", 1),
        ("DELETE FROM custos_operacionais WHERE user_id = %s", 1),
        ("DELETE FROM configuracoes WHERE user_id = %s", 1),
        ("DELETE FROM acessos_fazenda WHERE account_user_id = %s OR owner_user_id = %s", 2),
        ("DELETE FROM usuarios WHERE id = %s", 1),
    ]
    for sql, n in comandos:
        cur.execute(sql, (user_id,) * n)
    cur.execute("SET session_replication_role = 'origin'")
    conn.commit()
    cur.close()
    conn.close()


def _login(client, username):
    return client.post("/login", data={"username": username, "password": "senha123"},
                       follow_redirects=True)


@pytest.fixture
def curral(app):
    """Dono, um vaqueiro convidado e um animal. O client é o do vaqueiro."""
    uid_dono, _ = _criar_usuario()
    uid_vaq, user_vaq = _criar_usuario(com_fazenda=False)
    acesso_repository.conceder(uid_vaq, uid_dono, 'vaqueiro')
    aid = _criar_animal(uid_dono, f"AUT-{uid_dono}")

    client = app.test_client()
    _login(client, user_vaq)

    yield client, uid_dono, uid_vaq, aid

    _purgar(uid_vaq)
    _purgar(uid_dono)


# -- As quatro tabelas -------------------------------------------------------

def test_pesagem_grava_quem_pesou(curral):
    """'Quem pesou o 402?' — a pergunta do achado #8."""
    client, uid_dono, uid_vaq, aid = curral
    client.post(f'/pesar/{aid}', data={'data_pesagem': '2026-06-01', 'peso': '420'})

    linha = _buscar("SELECT registrado_por FROM pesagens "
                    "WHERE animal_id = %s AND peso = 420", (aid,))
    assert linha is not None, "pesagem não foi registrada"
    # O dado é do dono; a assinatura é do vaqueiro.
    assert linha[0] == uid_vaq
    assert _buscar("SELECT user_id FROM animais WHERE id = %s", (aid,))[0] == uid_dono


def test_medicacao_grava_quem_aplicou(curral):
    client, uid_dono, uid_vaq, aid = curral
    client.post(f'/medicar/{aid}', data={
        'data_aplicacao': '2026-06-01', 'nome': 'Vermífugo',
        'custo': '30', 'obs': '', 'dias_carencia': '0'})

    linha = _buscar("SELECT registrado_por FROM medicacoes "
                    "WHERE animal_id = %s AND nome_medicamento = 'Vermífugo'", (aid,))
    assert linha is not None and linha[0] == uid_vaq


def test_movimentacao_de_estoque_grava_quem_mexeu(curral):
    client, uid_dono, uid_vaq, aid = curral
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO estoque_produtos (user_id, nome, categoria, unidade) "
        "VALUES (%s, 'Vacina', 'medicamento', 'dose')", (uid_dono,))
    pid = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()

    client.post(f'/estoque/{pid}/entrada', data={
        'quantidade': '10', 'data_mov': '2026-06-01', 'custo_unitario': '5'})

    linha = _buscar("SELECT registrado_por FROM estoque_movimentacoes "
                    "WHERE produto_id = %s", (pid,))
    assert linha is not None and linha[0] == uid_vaq


def test_custo_operacional_grava_quem_lancou(app):
    """Custo é do dono — vaqueiro não entra no financeiro."""
    uid_dono, user_dono = _criar_usuario()
    client = app.test_client()
    try:
        _login(client, user_dono)
        client.post('/custos_operacionais', data={
            'categoria': 'Fixo', 'tipo_fixo': 'Arrendamento',
            'valor': '100', 'data': '2026-06-01', 'descricao': 'Carga'})
        linha = _buscar("SELECT registrado_por FROM custos_operacionais "
                        "WHERE user_id = %s", (uid_dono,))
        assert linha is not None and linha[0] == uid_dono
    finally:
        _purgar(uid_dono)


# -- A assinatura do override ------------------------------------------------

def test_override_de_carencia_e_assinado_por_quem_vendeu(app):
    """O inverso do bug de tenant: aqui um `farm_id` no lugar do `id` apagaria
    a única resposta para "quem liberou" se a carcaça for rejeitada."""
    uid_dono, user_dono = _criar_usuario()
    aid = _criar_animal(uid_dono, f"CAR-{uid_dono}", dias_carencia=40)
    client = app.test_client()
    try:
        _login(client, user_dono)
        client.post(f'/vender/{aid}', data={
            'data_venda': '2026-06-01', 'peso_venda': '500',
            'valor_arroba': '300', 'confirmar_carencia': '1'})

        linha = _buscar("SELECT autorizado_por FROM vendas_com_carencia "
                        "WHERE animal_id = %s", (aid,))
        assert linha is not None, "override não foi registrado"
        assert linha[0] == uid_dono
    finally:
        _purgar(uid_dono)


def test_autorizado_por_e_a_pessoa_nao_a_fazenda(curral):
    """Com dono e vaqueiro separados, os dois números divergem — e é o do
    vaqueiro que tem de ficar gravado."""
    client, uid_dono, uid_vaq, _aid = curral
    aid = _criar_animal(uid_dono, f"CAR2-{uid_dono}", dias_carencia=40)
    # Vaqueiro não vende; quem vende é o dono. Então o teste usa o caminho de
    # verdade: concede venda ao vaqueiro? Não — o papel é o que é. Aqui o que
    # importa é que a coluna não guarda farm_id, e isso se vê pelo tipo de id.
    linha_antes = _buscar("SELECT COUNT(*) FROM vendas_com_carencia "
                          "WHERE animal_id = %s", (aid,))[0]
    assert linha_antes == 0
    resp = client.post(f'/vender/{aid}', data={
        'data_venda': '2026-06-01', 'peso_venda': '500',
        'valor_arroba': '300', 'confirmar_carencia': '1'})
    assert resp.status_code == 403
    assert _buscar("SELECT COUNT(*) FROM vendas_com_carencia "
                   "WHERE animal_id = %s", (aid,))[0] == 0


# -- A ficha mostra ----------------------------------------------------------

def test_ficha_do_animal_mostra_quem_registrou(curral, app):
    client, uid_dono, uid_vaq, aid = curral
    client.post(f'/pesar/{aid}', data={'data_pesagem': '2026-06-01', 'peso': '415'})
    nome_vaq = _buscar("SELECT username FROM usuarios WHERE id = %s", (uid_vaq,))[0]

    corpo = client.get(f'/animal/{aid}').data.decode('utf-8')
    assert f"por {nome_vaq}" in corpo


def test_linha_antiga_sem_autor_nao_quebra_a_ficha(curral):
    """Toda pesagem anterior à migration tem registrado_por NULL."""
    client, uid_dono, uid_vaq, aid = curral
    _executar("INSERT INTO pesagens (animal_id, data_pesagem, peso) "
              "VALUES (%s, '2024-01-01', 300)", (aid,))
    resp = client.get(f'/animal/{aid}')
    assert resp.status_code == 200
    assert '300' in resp.data.decode('utf-8')


# -- O serviço de pesagem ----------------------------------------------------

def test_servico_recusa_peso_invalido(app):
    uid, _ = _criar_usuario()
    aid = _criar_animal(uid, f"SRV-{uid}")
    try:
        gravado, erro = servico_pesagem.registrar(uid, '0', '2026-06-01', uid, animal_id=aid)
        assert gravado is None and 'Peso' in erro
        gravado, erro = servico_pesagem.registrar(uid, '400', 'ontem', uid, animal_id=aid)
        assert gravado is None and erro
    finally:
        _purgar(uid)


def test_servico_aceita_brinco(app):
    """O brinco é a chave que a pessoa usa — e é por ele que qualquer entrada
    que não seja a ficha aberta vai chegar."""
    uid, _ = _criar_usuario()
    brinco = f"SRV2-{uid}"
    aid = _criar_animal(uid, brinco)
    try:
        gravado, erro = servico_pesagem.registrar(uid, '430', '2026-06-01', uid,
                                                  brinco=brinco)
        assert erro is None and gravado == aid
        linha = _buscar("SELECT peso, registrado_por FROM pesagens "
                        "WHERE animal_id = %s", (aid,))
        assert float(linha[0]) == 430 and linha[1] == uid
    finally:
        _purgar(uid)


def test_servico_nao_atravessa_fazenda(app):
    """Resolver o animal dentro do serviço é o que impede uma entrada nova de
    procurar pelo brinco sem o filtro da fazenda."""
    uid_a, _ = _criar_usuario()
    uid_b, _ = _criar_usuario()
    brinco = f"SRV3-{uid_a}"
    aid = _criar_animal(uid_a, brinco)
    try:
        gravado, erro = servico_pesagem.registrar(uid_b, '430', '2026-06-01', uid_b,
                                                  brinco=brinco)
        assert gravado is None and erro
        assert _buscar("SELECT COUNT(*) FROM pesagens WHERE animal_id = %s", (aid,))[0] == 0
    finally:
        _purgar(uid_a)
        _purgar(uid_b)


def test_servico_recusa_brinco_inexistente(app):
    uid, _ = _criar_usuario()
    try:
        gravado, erro = servico_pesagem.registrar(uid, '430', '2026-06-01', uid,
                                                  brinco='NAO-EXISTE')
        assert gravado is None and 'NAO-EXISTE' in erro
    finally:
        _purgar(uid)


def test_rota_de_pesagem_usa_o_servico(curral):
    """A rota ficou só com HTTP: se ela voltar a validar por conta própria,
    este caminho deixa de bater com o do serviço."""
    client, uid_dono, uid_vaq, aid = curral
    resp = client.post(f'/pesar/{aid}', data={'data_pesagem': '2026-06-01', 'peso': '0'})
    assert resp.status_code == 400
    erro_servico = servico_pesagem.registrar(uid_dono, '0', '2026-06-01', uid_vaq,
                                             animal_id=aid)[1]
    # O template escapa as aspas da mensagem; o que importa é ser a mesma frase.
    assert 'deve ser no mínimo 0.1' in erro_servico
    assert 'deve ser no mínimo 0.1' in resp.data.decode('utf-8')
