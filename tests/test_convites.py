"""Convite por email e seletor de fazenda.

Fecha o laço do PR dos acessos: até aqui `acessos_fazenda` só era alimentável
por SQL. O teste que vale a pena ler é
`test_convidado_define_senha_e_entra_na_fazenda_do_dono` — faz o caminho
inteiro, do convite ao painel do dono, usando o mesmo fluxo de código e
expiração do "esqueci minha senha".
"""
import itertools
import re

import pytest
from werkzeug.security import generate_password_hash

from models import User
from repositories import acesso_repository
from tests.dbcompat import connect

_seq = itertools.count(13000)


@pytest.fixture(autouse=True)
def sem_smtp(monkeypatch):
    """Nenhum teste manda email de verdade."""
    monkeypatch.setenv('MAIL_USERNAME', '')
    monkeypatch.setenv('MAIL_PASSWORD', '')


# -- Helpers -----------------------------------------------------------------

def _criar_dono(nome_fazenda=None):
    n = next(_seq)
    username = f"cv_{n}"
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash, email) VALUES (%s, %s, %s)",
        (username, generate_password_hash("senha123"), f"{username}@exemplo.com"),
    )
    uid = cur.lastrowid
    cur.execute("INSERT INTO configuracoes (user_id, nome_fazenda) VALUES (%s, %s)",
                (uid, nome_fazenda or f"Fazenda {n}"))
    conn.commit()
    cur.close()
    conn.close()
    return uid, username


def _criar_animal(user_id, brinco):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id)"
        " VALUES (%s, 'M', '2024-01-01', 1000, %s)",
        (brinco, user_id),
    )
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
        ("DELETE FROM pesagens p USING animais a"
         " WHERE p.animal_id = a.id AND a.user_id = %s", 1),
        ("DELETE FROM animais WHERE user_id = %s", 1),
        ("DELETE FROM configuracoes WHERE user_id = %s", 1),
        ("DELETE FROM password_reset_tokens WHERE user_id = %s", 1),
        ("DELETE FROM acessos_fazenda WHERE account_user_id = %s OR owner_user_id = %s", 2),
        ("DELETE FROM usuarios WHERE id = %s", 1),
    ]
    for sql, n in comandos:
        cur.execute(sql, (user_id,) * n)
    cur.execute("SET session_replication_role = 'origin'")
    conn.commit()
    cur.close()
    conn.close()


def _login(client, username, senha="senha123"):
    return client.post("/login", data={"username": username, "password": senha},
                       follow_redirects=True)


def _convidar(client, email, papel='vaqueiro'):
    return client.post('/acessos', data={'email': email, 'papel': papel})


def _conta_por_email(email):
    return _buscar("SELECT id, username FROM usuarios WHERE email = %s", (email,))


@pytest.fixture
def dono(app):
    uid, username = _criar_dono()
    client = app.test_client()
    _login(client, username)
    yield client, uid, username
    for linha in acesso_repository.listar_por_fazenda(uid):
        _purgar(linha[1])
    _purgar(uid)


# -- Username de sistema -----------------------------------------------------

def test_username_junta_fazenda_e_pessoa(app):
    assert acesso_repository.gerar_username('Fazenda Boa Esperança',
                                            'joao.silva@exemplo.com') == 'fazendaboaesperanca.joaosilva'


def test_username_sem_acento_e_sem_espaco(app):
    gerado = acesso_repository.gerar_username('Sítio São João', 'ana@x.com')
    assert re.fullmatch(r'[a-z0-9]+\.[a-z0-9]+', gerado), gerado


def test_username_desvia_de_colisao(app):
    """`usuarios.username` é UNIQUE global: a segunda fazenda a convidar um
    'joao' não pode quebrar o cadastro."""
    primeiro = acesso_repository.gerar_username('Fazenda X', 'joao@a.com')
    conn = connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO usuarios (username, password_hash) VALUES (%s, 'x')",
                (primeiro,))
    uid = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    try:
        segundo = acesso_repository.gerar_username('Fazenda X', 'joao@b.com')
        assert segundo != primeiro and segundo.startswith(primeiro)
    finally:
        _purgar(uid)


# -- O convite ---------------------------------------------------------------

def test_convite_cria_conta_acesso_e_codigo(dono):
    client, uid_dono, _ = dono
    email = f"novo{uid_dono}@exemplo.com"

    resp = _convidar(client, email, 'vaqueiro')
    assert resp.status_code == 200

    conta = _conta_por_email(email)
    assert conta is not None, "convite não criou a conta"
    assert conta[1].startswith('fazenda')

    acesso = _buscar("SELECT papel, ativo FROM acessos_fazenda "
                     "WHERE account_user_id = %s AND owner_user_id = %s",
                     (conta[0], uid_dono))
    assert acesso == ('vaqueiro', 1)

    # A primeira senha vem pelo mesmo fluxo de "esqueci minha senha".
    token = _buscar("SELECT code, used FROM password_reset_tokens WHERE user_id = %s",
                    (conta[0],))
    assert token is not None and token[1] == 0


def test_convidado_nasce_sem_fazenda_propria(dono):
    """É a ausência de linha em `configuracoes` que faz o convidado abrir na
    fazenda a que foi convidado, e não num rebanho vazio."""
    client, uid_dono, _ = dono
    email = f"semfazenda{uid_dono}@exemplo.com"
    _convidar(client, email)
    conta = _conta_por_email(email)
    assert _buscar("SELECT 1 FROM configuracoes WHERE user_id = %s", (conta[0],)) is None


def test_convite_para_quem_ja_tem_conta_nao_cria_outra(dono, app):
    client, uid_dono, _ = dono
    uid_outro, username_outro = _criar_dono()
    email = f"{username_outro}@exemplo.com"
    try:
        _convidar(client, email, 'contador')
        assert _buscar("SELECT COUNT(*) FROM usuarios WHERE email = %s", (email,))[0] == 1
        assert _buscar("SELECT papel FROM acessos_fazenda WHERE account_user_id = %s "
                       "AND owner_user_id = %s", (uid_outro, uid_dono))[0] == 'contador'
        # Quem já tinha conta não recebe código: a senha dele continua valendo.
        assert _buscar("SELECT COUNT(*) FROM password_reset_tokens WHERE user_id = %s",
                       (uid_outro,))[0] == 0
    finally:
        _executar("DELETE FROM acessos_fazenda WHERE account_user_id = %s", (uid_outro,))
        _purgar(uid_outro)


def test_nao_da_para_convidar_a_si_mesmo(dono):
    client, uid_dono, username = dono
    resp = _convidar(client, f"{username}@exemplo.com")
    assert 'você já é o dono'.encode('utf-8') in resp.data
    assert _buscar("SELECT COUNT(*) FROM acessos_fazenda WHERE owner_user_id = %s",
                   (uid_dono,))[0] == 0


@pytest.mark.parametrize('email,papel', [
    ('naoeemail', 'vaqueiro'),
    ('ok@exemplo.com', 'presidente'),
    ('ok@exemplo.com', 'dono'),
])
def test_convite_invalido_nao_cria_nada(dono, email, papel):
    client, uid_dono, _ = dono
    _convidar(client, email, papel)
    assert _buscar("SELECT COUNT(*) FROM acessos_fazenda WHERE owner_user_id = %s",
                   (uid_dono,))[0] == 0


def test_reconvidar_revogado_reativa(dono):
    """O vaqueiro da safra passada volta — e o UNIQUE recusaria um INSERT novo."""
    client, uid_dono, _ = dono
    email = f"volta{uid_dono}@exemplo.com"
    _convidar(client, email, 'vaqueiro')
    conta = _conta_por_email(email)
    _executar("UPDATE acessos_fazenda SET ativo = 0 WHERE account_user_id = %s", (conta[0],))

    _convidar(client, email, 'consultor')

    acesso = _buscar("SELECT papel, ativo, COUNT(*) OVER () FROM acessos_fazenda "
                     "WHERE account_user_id = %s", (conta[0],))
    assert acesso == ('consultor', 1, 1)


# -- Revogação ---------------------------------------------------------------

def test_revogar_derruba_o_acesso(dono, app):
    client, uid_dono, _ = dono
    email = f"rev{uid_dono}@exemplo.com"
    _convidar(client, email)
    conta = _conta_por_email(email)
    acesso_id = _buscar("SELECT id FROM acessos_fazenda WHERE account_user_id = %s",
                        (conta[0],))[0]

    client.post(f'/acessos/{acesso_id}/revogar')

    assert _buscar("SELECT ativo FROM acessos_fazenda WHERE id = %s", (acesso_id,))[0] == 0
    assert User.get_user_id(conta[0]).farm_id == conta[0]


def test_nao_revoga_acesso_de_outra_fazenda(dono, app):
    """O id vem da URL: sem o dono no WHERE, trocar o número mexeria na
    fazenda do vizinho."""
    client, uid_dono, _ = dono
    uid_vizinho, _ = _criar_dono()
    uid_convidado, _ = _criar_dono()
    acesso_id = acesso_repository.conceder(uid_convidado, uid_vizinho, 'vaqueiro')
    try:
        resp = client.post(f'/acessos/{acesso_id}/revogar', follow_redirects=True)
        assert resp.status_code == 200
        assert _buscar("SELECT ativo FROM acessos_fazenda WHERE id = %s", (acesso_id,))[0] == 1
    finally:
        _executar("DELETE FROM acessos_fazenda WHERE id = %s", (acesso_id,))
        _purgar(uid_convidado)
        _purgar(uid_vizinho)


def test_tela_de_acessos_e_do_dono(dono, app):
    client, uid_dono, _ = dono
    email = f"vaq{uid_dono}@exemplo.com"
    _convidar(client, email)
    conta = _conta_por_email(email)
    _executar("UPDATE usuarios SET password_hash = %s WHERE id = %s",
              (generate_password_hash('senha123'), conta[0]))

    client_vaq = app.test_client()
    _login(client_vaq, conta[1])
    assert client_vaq.get('/acessos').status_code == 403
    assert client_vaq.post(f'/acessos/1/revogar').status_code == 403


# -- O caminho inteiro -------------------------------------------------------

def test_convidado_define_senha_e_entra_na_fazenda_do_dono(dono, app):
    client, uid_dono, _ = dono
    brinco = f"DONO-{uid_dono}"
    _criar_animal(uid_dono, brinco)
    email = f"caminho{uid_dono}@exemplo.com"

    _convidar(client, email, 'vaqueiro')
    conta = _conta_por_email(email)
    codigo = _buscar("SELECT code FROM password_reset_tokens WHERE user_id = %s",
                     (conta[0],))[0]

    # O convidado usa o código do convite no mesmo fluxo de quem esqueceu a
    # senha — é a tela de verificação que recebe o código, e o email dele vem
    # do link do convite.
    convidado = app.test_client()
    with convidado.session_transaction() as sessao:
        sessao['reset_email'] = email
    resp = convidado.post('/verificar_codigo', data={'codigo': codigo},
                          follow_redirects=False)
    assert resp.status_code == 302, resp.data[:400]
    nova = convidado.post('/nova_senha', data={'password': 'novasenha1',
                                               'password_confirm': 'novasenha1'})
    assert nova.status_code == 302, nova.data[:400]

    entrada = app.test_client()
    _login(entrada, email, 'novasenha1')
    painel = entrada.get('/painel')
    assert painel.status_code == 200
    assert brinco.encode() in painel.data
    # E continua sendo vaqueiro: dinheiro não.
    assert entrada.get('/financeiro').status_code == 403


# -- Seletor de fazenda ------------------------------------------------------

def test_quem_tem_uma_fazenda_so_nao_ve_seletor(dono):
    client, uid_dono, _ = dono
    assert 'Fazenda ativa'.encode('utf-8') not in client.get('/painel').data


def test_consultor_de_duas_ve_e_troca(app):
    uid_a, _ = _criar_dono('Fazenda A')
    uid_b, _ = _criar_dono('Fazenda B')
    uid_cons, user_cons = _criar_dono('Fazenda Propria')
    acesso_repository.conceder(uid_cons, uid_a, 'consultor')
    acesso_repository.conceder(uid_cons, uid_b, 'consultor')
    _criar_animal(uid_a, f"A-{uid_a}")
    _criar_animal(uid_b, f"B-{uid_b}")
    client = app.test_client()
    try:
        _login(client, user_cons)
        painel = client.get('/painel')
        assert 'Fazenda ativa'.encode('utf-8') in painel.data
        assert 'Fazenda A'.encode('utf-8') in painel.data

        # Dono de si mesmo: abre na própria fazenda, não na do vizinho.
        assert f"A-{uid_a}".encode() not in painel.data

        client.post('/fazenda/trocar', data={'farm_id': uid_a})
        assert f"A-{uid_a}".encode() in client.get('/painel').data

        client.post('/fazenda/trocar', data={'farm_id': uid_b})
        dados = client.get('/painel').data
        assert f"B-{uid_b}".encode() in dados
        assert f"A-{uid_a}".encode() not in dados
    finally:
        _executar("DELETE FROM acessos_fazenda WHERE account_user_id = %s", (uid_cons,))
        _purgar(uid_cons)
        _purgar(uid_a)
        _purgar(uid_b)


def test_trocar_para_fazenda_sem_acesso_nao_vale(app):
    uid_a, _ = _criar_dono()
    uid_alheia, _ = _criar_dono()
    uid_cons, user_cons = _criar_dono()
    acesso_repository.conceder(uid_cons, uid_a, 'consultor')
    _criar_animal(uid_alheia, f"X-{uid_alheia}")
    client = app.test_client()
    try:
        _login(client, user_cons)
        client.post('/fazenda/trocar', data={'farm_id': uid_alheia})
        dados = client.get('/painel').data
        assert f"X-{uid_alheia}".encode() not in dados
    finally:
        _executar("DELETE FROM acessos_fazenda WHERE account_user_id = %s", (uid_cons,))
        _purgar(uid_cons)
        _purgar(uid_a)
        _purgar(uid_alheia)


def test_troca_limpa_o_nome_em_cache(app):
    """O cabeçalho mostra o nome da fazenda a partir da sessão — trocar sem
    limpar deixaria o nome da anterior na tela."""
    uid_a, _ = _criar_dono('Fazenda Primeira')
    uid_cons, user_cons = _criar_dono('Fazenda Propria')
    acesso_repository.conceder(uid_cons, uid_a, 'consultor')
    client = app.test_client()
    try:
        _login(client, user_cons)
        assert 'Fazenda Propria'.encode('utf-8') in client.get('/painel').data
        client.post('/fazenda/trocar', data={'farm_id': uid_a})
        # O nome da fazenda ativa fica na marca da barra lateral; as outras
        # aparecem no seletor, então a checagem é no cabeçalho, não na página.
        corpo = client.get('/painel').data.decode('utf-8')
        marca = re.search(r'barra-lateral__marca.*?<span>(.*?)</span>',
                          client.get('/painel').data.decode('utf-8'), re.S)
        assert marca and marca.group(1).strip() == 'Fazenda Primeira'
    finally:
        _executar("DELETE FROM acessos_fazenda WHERE account_user_id = %s", (uid_cons,))
        _purgar(uid_cons)
        _purgar(uid_a)


# -- Resolução da fazenda padrão ---------------------------------------------

def test_dono_convidado_abre_na_propria_fazenda():
    """Aceitar um convite não pode mudar a tela inicial de quem já tem
    fazenda."""
    assert User.resolver_fazenda(5, {9: 'contador'}, tem_fazenda_propria=True) == (5, 'dono')


def test_convidado_puro_abre_na_fazenda_do_convite():
    assert User.resolver_fazenda(5, {9: 'vaqueiro'}, tem_fazenda_propria=False) == (9, 'vaqueiro')


def test_escolher_a_propria_fazenda_vale():
    assert User.resolver_fazenda(5, {9: 'contador'}, escolhida=5,
                                 tem_fazenda_propria=True) == (5, 'dono')


# -- O menu não oferece o que a política nega --------------------------------

def test_menu_do_contador_nao_oferece_o_que_vai_dar_403(app):
    """Menu e porta saem da mesma POLICY: link que o papel não pode abrir não
    aparece, em vez de levar a pessoa a um 403."""
    uid_dono, _ = _criar_dono('Fazenda Cliente')
    uid_cont, user_cont = _criar_dono('Escritorio')
    acesso_repository.conceder(uid_cont, uid_dono, 'contador')
    client = app.test_client()
    try:
        _login(client, user_cont)
        client.post('/fazenda/trocar', data={'farm_id': uid_dono})
        corpo = client.get('/financeiro').data.decode('utf-8')

        assert '/financeiro' in corpo
        for negado in ('>Rebanho<', '>Pastos<', '>Estoque<', '>Sanidade<',
                       'Liberar acesso', 'Lixeira'):
            assert negado not in corpo, negado
        # A marca continua lá: ela é o logo, não item de navegação.
        assert 'barra-lateral__marca' in corpo
    finally:
        _executar("DELETE FROM acessos_fazenda WHERE account_user_id = %s", (uid_cont,))
        _purgar(uid_cont)
        _purgar(uid_dono)


def test_menu_do_dono_continua_inteiro(dono):
    client, uid_dono, _ = dono
    corpo = client.get('/painel').data.decode('utf-8')
    for item in ('>Rebanho<', '>Financeiro<', '>Pastos<', 'Lixeira', 'Registrar'):
        assert item in corpo, item


def test_vaqueiro_nao_ve_financeiro_no_menu(dono, app):
    client, uid_dono, _ = dono
    email = f"menu{uid_dono}@exemplo.com"
    _convidar(client, email, 'vaqueiro')
    conta = _conta_por_email(email)
    _executar("UPDATE usuarios SET password_hash = %s WHERE id = %s",
              (generate_password_hash('senha123'), conta[0]))
    vaq = app.test_client()
    _login(vaq, conta[1])
    corpo = vaq.get('/painel').data.decode('utf-8')
    assert '>Rebanho<' in corpo
    assert '>Financeiro<' not in corpo
    assert 'Lixeira' not in corpo
