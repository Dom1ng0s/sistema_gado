"""Acessos delegados e separação entre conta (`id`) e fazenda (`farm_id`).

O teste que pegaria o bug caro é
`test_apagar_conta_do_vaqueiro_nao_apaga_dados_do_dono`: a varredura que trocou
`current_user.id` por `current_user.farm_id` em routes/ passa por cima de
`apagar_conta`, e com `farm_id` ali um vaqueiro convidado confirmaria o próprio
username e levaria a fazenda do dono junto. O grep estrutural
(`test_identidade_nao_virou_tenant_nas_rotas`) impede a troca de voltar.
"""
import ast
import itertools
import os

import pytest
from werkzeug.security import generate_password_hash

from models import User
from tests.dbcompat import connect

_seq = itertools.count(7000)
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Onde `current_user.id` é certo: ato de identidade, não acesso a dado da
#: fazenda. Qualquer outra ocorrência é quase sempre bug de tenant.
IDENTIDADE_PERMITIDA = {
    ('routes/auth.py', 'apagar_conta'),
    # Quem assina o override de carência é a pessoa, não a fazenda: a tabela
    # existe para responder "quem liberou" se a carcaça for rejeitada.
    ('routes/operacional.py', 'vender'),
    ('routes/operacional.py', 'venda_lote'),
    # INSERT cru dentro da rota: a autoria entra posicionalmente na tupla, onde
    # o nome `registrado_por` não aparece para a varredura reconhecer.
    ('routes/operacional.py', 'importar_csv'),
}


# -- Helpers -----------------------------------------------------------------

def _criar_usuario(ativo=1):
    n = next(_seq)
    username = f"ac_{n}"
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash, ativo) VALUES (%s, %s, %s)",
        (username, generate_password_hash("senha123"), ativo),
    )
    uid = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return uid, username


def _conceder(account_user_id, owner_user_id, papel, ativo=1):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO acessos_fazenda (account_user_id, owner_user_id, papel, ativo)"
        " VALUES (%s, %s, %s, %s)",
        (account_user_id, owner_user_id, papel, ativo),
    )
    conn.commit()
    cur.close()
    conn.close()


def _executar(sql, params=()):
    conn = connect()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    cur.close()
    conn.close()


def _buscar(sql, params=()):
    conn = connect()
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def _criar_animal(user_id, brinco):
    conn = connect()
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


def _purgar(user_id):
    conn = connect()
    cur = conn.cursor()
    cur.execute("SET session_replication_role = 'replica'")
    comandos = [
        ("DELETE FROM pesagens p USING animais a"
         " WHERE p.animal_id = a.id AND a.user_id = %s", 1),
        ("DELETE FROM medicacoes m USING animais a"
         " WHERE m.animal_id = a.id AND a.user_id = %s", 1),
        ("DELETE FROM animais WHERE user_id = %s", 1),
        ("DELETE FROM configuracoes WHERE user_id = %s", 1),
        # replication_role='replica' desliga as FKs, então o CASCADE de
        # acessos_fazenda não dispara: apaga à mão para não deixar órfão.
        ("DELETE FROM acessos_fazenda"
         " WHERE account_user_id = %s OR owner_user_id = %s", 2),
        ("DELETE FROM usuarios WHERE id = %s", 1),
    ]
    for sql, n in comandos:
        cur.execute(sql, (user_id,) * n)
    cur.execute("SET session_replication_role = 'origin'")
    conn.commit()
    cur.close()
    conn.close()


def _login(client, username):
    return client.post("/login",
                       data={"username": username, "password": "senha123"},
                       follow_redirects=True)


@pytest.fixture
def fazenda(app):
    """Dono com um animal, e um vaqueiro convidado nessa fazenda.

    Yield: (client_vaqueiro, uid_dono, uid_vaqueiro, user_vaqueiro, brinco, animal_id)
    """
    uid_dono, _ = _criar_usuario()
    uid_vaq, user_vaq = _criar_usuario()
    _conceder(uid_vaq, uid_dono, 'vaqueiro')
    brinco = f"DONO-{uid_dono}"
    aid = _criar_animal(uid_dono, brinco)

    client = app.test_client()
    _login(client, user_vaq)

    yield client, uid_dono, uid_vaq, user_vaq, brinco, aid

    _purgar(uid_vaq)
    _purgar(uid_dono)


# -- A varredura: identidade não pode ter virado tenant ----------------------

def _ocorrencias_de_current_user_id():
    """(arquivo, função) de todo `current_user.id` no código de aplicação."""
    arquivos = ['app.py']
    for pasta in ('routes', 'utils', 'repositories'):
        for nome in sorted(os.listdir(os.path.join(RAIZ, pasta))):
            if nome.endswith('.py'):
                arquivos.append(f"{pasta}/{nome}")

    achados = []
    for rel in arquivos:
        with open(os.path.join(RAIZ, rel), encoding='utf-8') as fh:
            arvore = ast.parse(fh.read())

        # `registrado_por=current_user.id` é autoria declarada, não tenant: a
        # pessoa que fez o registro. A varredura reconhece pelo nome do
        # argumento, então um ponto de escrita novo nasce coberto sem precisar
        # entrar em allowlist nenhuma.
        autoria = {id(kw.value) for kw in ast.walk(arvore)
                   if isinstance(kw, ast.keyword) and kw.arg == 'registrado_por'}

        for no in ast.walk(arvore):
            if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for interno in ast.walk(no):
                if (isinstance(interno, ast.Attribute) and interno.attr == 'id'
                        and isinstance(interno.value, ast.Name)
                        and interno.value.id == 'current_user'
                        and id(interno) not in autoria):
                    achados.append((rel, no.name))
    return achados


def test_identidade_nao_virou_tenant_nas_rotas():
    fora = sorted(set(_ocorrencias_de_current_user_id()) - IDENTIDADE_PERMITIDA)
    assert not fora, (
        "current_user.id fora da allowlist — use current_user.farm_id para dado "
        f"da fazenda: {fora}"
    )


def test_autoria_declarada_nao_entra_na_varredura():
    """`registrado_por=current_user.id` não é bug de tenant — e a varredura
    precisa saber disso sem que cada ponto de escrita vire exceção."""
    achados = _ocorrencias_de_current_user_id()
    assert ('routes/operacional.py', 'nova_pesagem') not in achados
    assert ('routes/estoque.py', 'registrar_saida') not in achados


def test_allowlist_nao_tem_entrada_morta():
    """Entrada que não corresponde a nenhuma ocorrência real esconde o próximo
    caso de identidade legítimo."""
    reais = set(_ocorrencias_de_current_user_id())
    assert not (IDENTIDADE_PERMITIDA - reais)


def test_templates_nao_usam_current_user_id():
    pasta = os.path.join(RAIZ, 'templates')
    sujos = []
    for nome in sorted(os.listdir(pasta)):
        if not nome.endswith('.html'):
            continue
        with open(os.path.join(pasta, nome), encoding='utf-8') as fh:
            if 'current_user.id' in fh.read():
                sujos.append(nome)
    assert not sujos


# -- resolver_fazenda: a revalidação, sem banco ------------------------------

def test_sem_acesso_a_fazenda_e_a_propria_conta():
    assert User.resolver_fazenda(5, {}) == (5, 'dono')
    assert User.resolver_fazenda(5, {}, escolhida=99) == (5, 'dono')


def test_escolha_valida_e_respeitada():
    acessos = {10: 'consultor', 20: 'consultor'}
    assert User.resolver_fazenda(5, acessos, escolhida=20) == (20, 'consultor')


def test_escolha_invalida_nao_abre_fazenda_alheia():
    """O ponto da revalidação: valor que não voltou do banco é descartado."""
    acessos = {10: 'vaqueiro'}
    assert User.resolver_fazenda(5, acessos, escolhida=777) == (10, 'vaqueiro')
    assert User.resolver_fazenda(5, acessos, escolhida=None) == (10, 'vaqueiro')


# -- loader ------------------------------------------------------------------

def test_dono_tem_farm_id_igual_ao_id(app):
    uid, _ = _criar_usuario()
    try:
        u = User.get_user_id(uid)
        assert (u.id, u.farm_id, u.papel) == (uid, uid, 'dono')
    finally:
        _purgar(uid)


def test_vaqueiro_carrega_fazenda_do_dono(app):
    uid_dono, _ = _criar_usuario()
    uid_vaq, _ = _criar_usuario()
    _conceder(uid_vaq, uid_dono, 'vaqueiro')
    try:
        u = User.get_user_id(uid_vaq)
        assert u.id == uid_vaq
        assert u.farm_id == uid_dono
        assert u.papel == 'vaqueiro'
    finally:
        _purgar(uid_vaq)
        _purgar(uid_dono)


def test_acesso_revogado_volta_para_a_propria_conta(app):
    uid_dono, _ = _criar_usuario()
    uid_vaq, _ = _criar_usuario()
    _conceder(uid_vaq, uid_dono, 'vaqueiro')
    try:
        assert User.get_user_id(uid_vaq).farm_id == uid_dono
        _executar("UPDATE acessos_fazenda SET ativo = 0 WHERE account_user_id = %s",
                  (uid_vaq,))
        u = User.get_user_id(uid_vaq)
        assert (u.farm_id, u.papel) == (uid_vaq, 'dono')
    finally:
        _purgar(uid_vaq)
        _purgar(uid_dono)


def test_conta_desativada_nao_carrega(app):
    uid, _ = _criar_usuario(ativo=0)
    try:
        assert User.get_user_id(uid) is None
    finally:
        _purgar(uid)


def test_conta_desativada_nao_loga(app):
    uid, username = _criar_usuario(ativo=0)
    client = app.test_client()
    try:
        resp = _login(client, username)
        assert 'incorretos' in resp.data.decode('utf-8')
    finally:
        _purgar(uid)


def test_login_nao_herda_a_sessao_do_usuario_anterior(app):
    """Trocar de conta no mesmo navegador não pode deixar o cabeçalho na
    fazenda antiga: inject_user_info guarda o nome em cache na sessão."""
    uid, username = _criar_usuario()
    client = app.test_client()
    try:
        _executar("INSERT INTO configuracoes (user_id, nome_fazenda) VALUES (%s, %s)",
                  (uid, 'Fazenda Certa'))
        with client.session_transaction() as sessao:
            sessao['nome_fazenda'] = 'Fazenda De Outro'
            sessao['farm_id'] = 999999
        _login(client, username)
        corpo = client.get('/painel').data.decode('utf-8')
        assert 'Fazenda De Outro' not in corpo
        assert 'Fazenda Certa' in corpo
    finally:
        _executar("DELETE FROM configuracoes WHERE user_id = %s", (uid,))
        _purgar(uid)


# -- HTTP: o vaqueiro dentro da fazenda --------------------------------------

def test_vaqueiro_ve_o_rebanho_do_dono(fazenda):
    client, uid_dono, uid_vaq, user_vaq, brinco, aid = fazenda
    resp = client.get('/painel')
    assert resp.status_code == 200
    assert brinco.encode() in resp.data


@pytest.mark.parametrize('url', ['/financeiro', '/configuracoes', '/lixeira'])
def test_vaqueiro_toma_403_no_que_nao_e_dele(fazenda, url):
    client = fazenda[0]
    assert client.get(url).status_code == 403


def test_vaqueiro_nao_vende(fazenda):
    client, uid_dono, uid_vaq, user_vaq, brinco, aid = fazenda
    resp = client.post(f'/vender/{aid}',
                       data={'data_venda': '2024-06-01', 'peso_venda': '500',
                             'valor_arroba': '300'})
    assert resp.status_code == 403
    assert _buscar("SELECT data_venda FROM animais WHERE id = %s", (aid,))[0] is None


def test_vaqueiro_nao_le_fazenda_de_terceiro(fazenda):
    client = fazenda[0]
    uid_c, _ = _criar_usuario()
    brinco_c = f"TERCEIRO-{uid_c}"
    _criar_animal(uid_c, brinco_c)
    try:
        assert brinco_c.encode() not in client.get('/painel').data
    finally:
        _purgar(uid_c)


def test_vaqueiro_pode_pesar_na_fazenda_do_dono(fazenda):
    client, uid_dono, uid_vaq, user_vaq, brinco, aid = fazenda
    antes = _buscar("SELECT COUNT(*) FROM pesagens WHERE animal_id = %s", (aid,))[0]
    client.post(f'/pesar/{aid}', data={'data_pesagem': '2024-06-01', 'peso': '400'})
    depois = _buscar("SELECT COUNT(*) FROM pesagens WHERE animal_id = %s", (aid,))[0]
    assert depois == antes + 1


def test_apagar_conta_do_vaqueiro_nao_apaga_dados_do_dono(fazenda):
    """O bug que a varredura criaria: `apagar_conta` com farm_id apagaria a
    fazenda inteira do dono quando o convidado sai."""
    client, uid_dono, uid_vaq, user_vaq, brinco, aid = fazenda

    client.post('/conta/apagar', data={'confirmacao': user_vaq})

    assert _buscar("SELECT id FROM usuarios WHERE id = %s", (uid_vaq,)) is None
    assert _buscar("SELECT id FROM usuarios WHERE id = %s", (uid_dono,)) is not None
    assert _buscar("SELECT brinco FROM animais WHERE id = %s", (aid,))[0] == brinco
    # O acesso morre com a conta pelo ON DELETE CASCADE.
    assert _buscar("SELECT COUNT(*) FROM acessos_fazenda WHERE account_user_id = %s",
                   (uid_vaq,))[0] == 0


def test_revogar_acesso_derruba_a_sessao_no_request_seguinte(fazenda):
    client, uid_dono, uid_vaq, user_vaq, brinco, aid = fazenda
    assert brinco.encode() in client.get('/painel').data

    _executar("UPDATE acessos_fazenda SET ativo = 0 WHERE account_user_id = %s",
              (uid_vaq,))

    # Mesmo cookie, request seguinte: o loader resolve de novo e o vaqueiro
    # volta a ser dono da própria conta vazia.
    assert brinco.encode() not in client.get('/painel').data


def test_desativar_conta_derruba_a_sessao_no_request_seguinte(fazenda):
    client, uid_dono, uid_vaq, user_vaq, brinco, aid = fazenda
    _executar("UPDATE usuarios SET ativo = 0 WHERE id = %s", (uid_vaq,))
    resp = client.get('/painel')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_contador_le_dinheiro_e_nao_entra_no_rebanho(app):
    uid_dono, _ = _criar_usuario()
    uid_cont, user_cont = _criar_usuario()
    _conceder(uid_cont, uid_dono, 'contador')
    client = app.test_client()
    try:
        _login(client, user_cont)
        assert client.get('/financeiro').status_code == 200
        assert client.get('/painel').status_code == 403
    finally:
        _purgar(uid_cont)
        _purgar(uid_dono)


def test_consultor_de_duas_fazendas_fica_em_uma_e_nao_mistura(app):
    uid_a, _ = _criar_usuario()
    uid_b, _ = _criar_usuario()
    uid_cons, user_cons = _criar_usuario()
    _conceder(uid_cons, uid_a, 'consultor')
    _conceder(uid_cons, uid_b, 'consultor')
    brinco_a = f"FAZ-A-{uid_a}"
    brinco_b = f"FAZ-B-{uid_b}"
    _criar_animal(uid_a, brinco_a)
    _criar_animal(uid_b, brinco_b)
    client = app.test_client()
    try:
        _login(client, user_cons)
        dados = client.get('/painel').data
        # O seletor de fazenda vem depois; o que não pode é ver as duas juntas.
        assert (brinco_a.encode() in dados) != (brinco_b.encode() in dados)
    finally:
        _purgar(uid_cons)
        _purgar(uid_a)
        _purgar(uid_b)


# -- schema ------------------------------------------------------------------

@pytest.mark.parametrize('tabela', ['pesagens', 'medicacoes', 'custos_operacionais',
                                    'estoque_movimentacoes'])
def test_registrado_por_existe(app, tabela):
    assert _buscar(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = 'registrado_por'", (tabela,)
    ) is not None


def test_papel_invalido_e_barrado_pelo_check(app):
    import psycopg
    uid_dono, _ = _criar_usuario()
    uid_x, _ = _criar_usuario()
    try:
        with pytest.raises(psycopg.errors.CheckViolation):
            _conceder(uid_x, uid_dono, 'presidente')
    finally:
        _purgar(uid_x)
        _purgar(uid_dono)
