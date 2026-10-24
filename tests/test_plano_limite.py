"""Plano da fazenda: trial, limite de cabeças e ativação manual.

Duas invariantes carregam o PR. A primeira é que o limite **nunca esconde
animal existente**: a fazenda que passou do limite continua vendo e editando
tudo o que já cadastrou, só não cadastra mais
(`test_limite_estourado_nao_esconde_rebanho`). A segunda é que o limite vale
nos três caminhos de entrada, não só no formulário de um animal — lote e CSV
entram centenas de cabeças de uma vez, e um limite que só olha o cadastro
avulso não é limite.
"""
import io
import itertools
from datetime import datetime, timedelta, timezone

import pytest
from werkzeug.security import generate_password_hash

from repositories import configuracao_repository
from tests.dbcompat import connect
from utils import plano as plano_regras

_seq = itertools.count(11000)


# -- Helpers -----------------------------------------------------------------

def _criar_dono(limite=None, tier='porteira', trial_ends_at=None, com_config=True):
    """Dono com linha de configuração já no plano desejado."""
    n = next(_seq)
    username = f"pl_{n}"
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
        (username, generate_password_hash("senha123")),
    )
    uid = cur.lastrowid
    if com_config:
        cur.execute(
            "INSERT INTO configuracoes (user_id, nome_fazenda, plano_tier, "
            "trial_ends_at, limite_cabecas) VALUES (%s, %s, %s, %s, %s)",
            (uid, f"Fazenda {n}", tier, trial_ends_at,
             plano_regras.LIMITE_PADRAO if limite is None else limite),
        )
    conn.commit()
    cur.close()
    conn.close()
    return uid, username


def _criar_animal(user_id, brinco, vendido=False):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id, data_venda)"
        " VALUES (%s, 'M', '2024-01-01', 1000, %s, %s)",
        (brinco, user_id, '2024-06-01' if vendido else None),
    )
    aid = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return aid


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


def _purgar(user_id):
    conn = connect()
    cur = conn.cursor()
    cur.execute("SET session_replication_role = 'replica'")
    for sql in [
        "DELETE FROM pesagens p USING animais a WHERE p.animal_id = a.id AND a.user_id = %s",
        "DELETE FROM animais WHERE user_id = %s",
        "DELETE FROM pagamentos WHERE user_id = %s",
        "DELETE FROM configuracoes WHERE user_id = %s",
        "DELETE FROM usuarios WHERE id = %s",
    ]:
        cur.execute(sql, (user_id,))
    cur.execute("SET session_replication_role = 'origin'")
    conn.commit()
    cur.close()
    conn.close()


def _login(client, username):
    return client.post("/login",
                       data={"username": username, "password": "senha123"},
                       follow_redirects=True)


def _csv(linhas):
    cabecalho = "brinco,sexo,data_compra,peso_kg,valor_arroba\n"
    corpo = "".join(f"{b},M,2026-01-10,300,185.00\n" for b in linhas)
    return (cabecalho + corpo).encode('utf-8')


def _importar(client, brincos):
    return client.post("/importar-csv",
                       data={"arquivo": (io.BytesIO(_csv(brincos)), "animais.csv")},
                       content_type='multipart/form-data')


def _contar_animais(user_id):
    return _buscar("SELECT COUNT(*) FROM animais WHERE user_id = %s AND deleted_at IS NULL",
                   (user_id,))[0]


# -- Regras, sem banco -------------------------------------------------------

def _plano(tier='trial', dias=None, limite=250, status='ativo'):
    fim = None if dias is None else datetime.now(timezone.utc) + timedelta(days=dias)
    return {'tier': tier, 'status': status, 'trial_ends_at': fim, 'limite_cabecas': limite}


def test_dias_restantes_arredonda_para_cima():
    """Faltando algumas horas, o dono ainda está no último dia — não em zero."""
    assert plano_regras.dias_restantes(_plano(dias=13.5)) == 14
    assert plano_regras.dias_restantes(_plano(dias=0.2)) == 1


def test_fora_do_trial_nao_tem_contagem():
    assert plano_regras.dias_restantes(_plano(tier='porteira', dias=None)) is None
    # tier trial sem data não é trial: não há até quando
    assert plano_regras.dias_restantes(_plano(tier='trial', dias=None)) is None
    assert not plano_regras.trial_expirado(_plano(tier='porteira'))


def test_trial_vencido():
    assert plano_regras.trial_expirado(_plano(dias=-1))
    assert not plano_regras.trial_expirado(_plano(dias=1))


def test_limite_zero_ou_negativo_e_sem_limite():
    """A saída da conta negociada à mão, para ninguém ter de inventar 999999."""
    assert plano_regras.sem_limite(_plano(limite=0))
    assert plano_regras.sem_limite(_plano(limite=-1))
    assert plano_regras.sem_limite({'tier': 'x', 'status': 'ativo',
                                    'trial_ends_at': None, 'limite_cabecas': None})
    assert plano_regras.vagas(_plano(limite=0), 9000) is None
    assert plano_regras.pode_cadastrar(_plano(limite=0), 9000, 500)[0]


def test_vagas_negativas_quando_rebanho_passou_do_limite():
    assert plano_regras.vagas(_plano(limite=250), 400) == -150


def test_pode_cadastrar_respeita_a_borda():
    assert plano_regras.pode_cadastrar(_plano(limite=10), 9, 1)[0]
    assert not plano_regras.pode_cadastrar(_plano(limite=10), 10, 1)[0]
    assert plano_regras.pode_cadastrar(_plano(limite=10), 5, 5)[0]
    assert not plano_regras.pode_cadastrar(_plano(limite=10), 5, 6)[0]


def test_mensagem_diz_o_numero_e_a_saida():
    _, msg = plano_regras.pode_cadastrar(_plano(limite=10), 10, 1)
    assert '10' in msg and 'Plano' in msg
    _, msg_lote = plano_regras.pode_cadastrar(_plano(limite=10), 8, 5)
    assert '2 vaga' in msg_lote and '5' in msg_lote


def test_resumo_para_a_tela():
    r = plano_regras.resumo(_plano(limite=200), 150)
    assert (r['vagas'], r['uso_pct'], r['estourado']) == (50, 75, False)
    cheio = plano_regras.resumo(_plano(limite=200), 260)
    assert cheio['estourado'] and cheio['uso_pct'] == 100
    livre = plano_regras.resumo(_plano(limite=0), 9000)
    assert livre['sem_limite'] and livre['uso_pct'] is None


# -- Leitura do plano --------------------------------------------------------

def test_conta_sem_configuracao_cai_no_padrao(app):
    """Ausência de configuração é falha nossa, não inadimplência do cliente."""
    uid, _ = _criar_dono(com_config=False)
    try:
        assert configuracao_repository.get_plano(uid) == plano_regras.PLANO_PADRAO
    finally:
        _purgar(uid)


def test_get_plano_le_o_que_esta_no_banco(app):
    uid, _ = _criar_dono(limite=42, tier='sede')
    try:
        p = configuracao_repository.get_plano(uid)
        assert (p['tier'], p['limite_cabecas'], p['status']) == ('sede', 42, 'ativo')
    finally:
        _purgar(uid)


def test_hook_do_plano_esta_registrado(app):
    nomes = [f.__name__ for f in app.before_request_funcs.get(None, [])]
    assert 'carregar_plano' in nomes


def test_plano_e_lido_por_request_nao_da_sessao(app):
    """Mudar o plano no banco vale na requisição seguinte, sem novo login —
    é por isso que o valor não é carimbado na sessão."""
    uid, username = _criar_dono(limite=50)
    client = app.test_client()
    try:
        _login(client, username)
        assert b'50' in client.get('/plano').data
        _executar("UPDATE configuracoes SET limite_cabecas = 77 WHERE user_id = %s", (uid,))
        assert b'77' in client.get('/plano').data
    finally:
        _purgar(uid)


def test_cadastro_novo_entra_em_trial(app, client):
    n = next(_seq)
    username = f"pl_novo_{n}"
    client.post('/novo_usuario', data={
        'username': username, 'password': 'senha123',
        'email': f"{username}@exemplo.com", 'nome_fazenda': 'Nova',
    })
    linha = _buscar("SELECT id FROM usuarios WHERE username = %s", (username,))
    assert linha is not None, "cadastro não criou a conta"
    uid = linha[0]
    try:
        plano = configuracao_repository.get_plano(uid)
        assert plano['tier'] == 'trial'
        dias = plano_regras.dias_restantes(plano)
        assert dias == plano_regras.TRIAL_DIAS
    finally:
        _purgar(uid)


# -- O limite nos três caminhos de entrada -----------------------------------

def test_cadastro_avulso_barra_no_limite(app):
    uid, username = _criar_dono(limite=1)
    _criar_animal(uid, f"CHEIO-{uid}")
    client = app.test_client()
    try:
        _login(client, username)
        resp = client.post('/cadastro', data={
            'brinco': f"NOVO-{uid}", 'sexo': 'M', 'data_compra': '2026-01-10',
        })
        assert resp.status_code == 403
        assert 'Plano'.encode('utf-8') in resp.data
        assert _contar_animais(uid) == 1
    finally:
        _purgar(uid)


def test_cadastro_de_lote_nao_e_porta_de_fuga(app):
    """O lote entra N cabeças de uma vez: ou o limite conta N, ou não existe."""
    uid, username = _criar_dono(limite=2)
    client = app.test_client()
    try:
        _login(client, username)
        resp = client.post('/cadastro-lote', data={
            'codigo_lote': f"L-{uid}", 'data_compra': '2026-01-10',
            'valor_arroba': '180', 'descricao': '',
            'brincos[]': [f"L{uid}-1", f"L{uid}-2", f"L{uid}-3"],
            'sexos[]': ['M', 'M', 'M'],
            'pesos[]': ['300', '310', '320'],
        })
        assert resp.status_code == 403
        assert _contar_animais(uid) == 0
    finally:
        _purgar(uid)


def test_lote_que_cabe_passa(app):
    uid, username = _criar_dono(limite=3)
    client = app.test_client()
    try:
        _login(client, username)
        client.post('/cadastro-lote', data={
            'codigo_lote': f"L-{uid}", 'data_compra': '2026-01-10',
            'valor_arroba': '180', 'descricao': '',
            'brincos[]': [f"K{uid}-1", f"K{uid}-2", f"K{uid}-3"],
            'sexos[]': ['M', 'M', 'M'],
            'pesos[]': ['300', '310', '320'],
        })
        assert _contar_animais(uid) == 3
    finally:
        _purgar(uid)


def test_csv_importa_o_que_cabe_e_reporta_o_resto(app):
    """Arquivo grande não é perdido inteiro: importa até a última vaga e diz,
    linha por linha, o que ficou fora — mesmo tratamento do limite de linhas."""
    uid, username = _criar_dono(limite=2)
    client = app.test_client()
    try:
        _login(client, username)
        resp = _importar(client, [f"C{uid}-1", f"C{uid}-2", f"C{uid}-3"])
        assert resp.status_code == 200
        assert _contar_animais(uid) == 2
        assert 'limite do plano'.encode('utf-8') in resp.data
    finally:
        _purgar(uid)


def test_csv_sem_vaga_nenhuma_e_recusado(app):
    uid, username = _criar_dono(limite=1)
    _criar_animal(uid, f"UNICO-{uid}")
    client = app.test_client()
    try:
        _login(client, username)
        resp = _importar(client, [f"D{uid}-1", f"D{uid}-2"])
        assert resp.status_code == 403
        assert _contar_animais(uid) == 1
    finally:
        _purgar(uid)


def test_csv_dentro_do_limite_importa_tudo(app):
    uid, username = _criar_dono(limite=5)
    client = app.test_client()
    try:
        _login(client, username)
        resp = _importar(client, [f"E{uid}-1", f"E{uid}-2"])
        assert resp.status_code == 200
        assert _contar_animais(uid) == 2
    finally:
        _purgar(uid)


# -- O limite não toca no que já existe --------------------------------------

def test_limite_estourado_nao_esconde_rebanho(app):
    """Plano apertado depois do cadastro não faz animal desaparecer: o dono
    continua vendo e abrindo a ficha de tudo o que já é dele."""
    uid, username = _criar_dono(limite=1)
    brincos = [f"VELHO{uid}-{i}" for i in range(3)]
    ids = [_criar_animal(uid, b) for b in brincos]
    client = app.test_client()
    try:
        _login(client, username)
        painel = client.get('/painel')
        assert painel.status_code == 200
        for b in brincos:
            assert b.encode() in painel.data
        assert client.get(f'/animal/{ids[0]}').status_code == 200
    finally:
        _purgar(uid)


def test_vender_libera_vaga(app):
    """Cabeça vendida não conta: é o que faz o limite ser sobre o rebanho que a
    fazenda administra, não sobre o histórico."""
    uid, username = _criar_dono(limite=1)
    _criar_animal(uid, f"VENDIDO-{uid}", vendido=True)
    client = app.test_client()
    try:
        _login(client, username)
        resp = client.post('/cadastro', data={
            'brinco': f"ENTRA-{uid}", 'sexo': 'M', 'data_compra': '2026-01-10',
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert _contar_animais(uid) == 2
    finally:
        _purgar(uid)


def test_excluido_nao_conta(app):
    uid, username = _criar_dono(limite=1)
    aid = _criar_animal(uid, f"LIXO-{uid}")
    _executar("UPDATE animais SET deleted_at = now() WHERE id = %s", (aid,))
    client = app.test_client()
    try:
        _login(client, username)
        resp = client.post('/cadastro', data={
            'brinco': f"POSLIXO-{uid}", 'sexo': 'M', 'data_compra': '2026-01-10',
        }, follow_redirects=True)
        assert resp.status_code == 200
    finally:
        _purgar(uid)


# -- Tela do plano -----------------------------------------------------------

def test_tela_do_plano_mostra_uso(app):
    uid, username = _criar_dono(limite=10)
    _criar_animal(uid, f"T-{uid}")
    client = app.test_client()
    try:
        _login(client, username)
        resp = client.get('/plano')
        assert resp.status_code == 200
        assert b'10' in resp.data
    finally:
        _purgar(uid)


def test_tela_do_plano_no_trial_mostra_o_vencimento(app):
    """Renderiza o galho de trial do template: aviso, badge e a data."""
    fim = datetime.now(timezone.utc) + timedelta(days=3)
    uid, username = _criar_dono(tier='trial', trial_ends_at=fim, limite=10)
    client = app.test_client()
    try:
        _login(client, username)
        resp = client.get('/plano')
        assert resp.status_code == 200
        corpo = resp.data.decode('utf-8')
        assert 'dia(s) de avaliação' in corpo
        # A data sai no fuso da sessão do banco, que é o da fazenda — por isso
        # a referência é o valor relido, não o datetime UTC que o teste montou.
        gravado = configuracao_repository.get_plano(uid)['trial_ends_at']
        assert gravado.strftime('%d/%m/%Y') in corpo
    finally:
        _purgar(uid)


def test_tela_do_plano_vencido_avisa_sem_assustar(app):
    """Trial vencido diz, na mesma tela, que os dados continuam lá."""
    fim = datetime.now(timezone.utc) - timedelta(days=1)
    uid, username = _criar_dono(tier='trial', trial_ends_at=fim, limite=10)
    client = app.test_client()
    try:
        _login(client, username)
        corpo = client.get('/plano').data.decode('utf-8')
        assert 'avaliação encerrado' in corpo
        assert 'continuam aqui' in corpo
    finally:
        _purgar(uid)


def test_tela_do_plano_sem_limite(app):
    uid, username = _criar_dono(limite=0)
    client = app.test_client()
    try:
        _login(client, username)
        corpo = client.get('/plano').data.decode('utf-8')
        assert 'sem limite' in corpo
    finally:
        _purgar(uid)


def test_tela_do_plano_e_do_dono(app):
    """Papel de campo não administra assinatura — a política barra antes."""
    uid_dono, _ = _criar_dono()
    uid_vaq, user_vaq = _criar_dono(com_config=False)
    _executar("INSERT INTO acessos_fazenda (account_user_id, owner_user_id, papel)"
              " VALUES (%s, %s, 'vaqueiro')", (uid_vaq, uid_dono))
    client = app.test_client()
    try:
        _login(client, user_vaq)
        assert client.get('/plano').status_code == 403
    finally:
        _executar("DELETE FROM acessos_fazenda WHERE account_user_id = %s", (uid_vaq,))
        _purgar(uid_vaq)
        _purgar(uid_dono)


# -- Ativação manual --------------------------------------------------------

def test_ativar_plano_encerra_o_trial(app):
    fim = datetime.now(timezone.utc) + timedelta(days=5)
    uid, _ = _criar_dono(tier='trial', trial_ends_at=fim, limite=250)
    try:
        assert configuracao_repository.ativar_plano(uid, 'sede', 1000)
        p = configuracao_repository.get_plano(uid)
        assert (p['tier'], p['limite_cabecas'], p['trial_ends_at']) == ('sede', 1000, None)
        assert plano_regras.dias_restantes(p) is None
    finally:
        _purgar(uid)


def test_ativar_plano_sem_configuracao_avisa(app):
    uid, _ = _criar_dono(com_config=False)
    try:
        assert configuracao_repository.ativar_plano(uid, 'sede', 1000) is False
    finally:
        _purgar(uid)


def test_pagamento_e_idempotente(app):
    """O UNIQUE é o que impede o operador de ativar duas vezes a mesma cobrança
    — e é o mesmo mecanismo que vai engolir o reenvio do webhook."""
    uid, _ = _criar_dono()
    try:
        assert configuracao_repository.registrar_pagamento(
            uid, 'asaas', f"pay_{uid}", 149.90, 'confirmado', payload={'x': 1})
        assert not configuracao_repository.registrar_pagamento(
            uid, 'asaas', f"pay_{uid}", 149.90, 'confirmado')
        assert _buscar("SELECT COUNT(*) FROM pagamentos WHERE user_id = %s", (uid,))[0] == 1
    finally:
        _purgar(uid)


def test_payload_fica_gravado_como_jsonb(app):
    uid, _ = _criar_dono()
    try:
        configuracao_repository.registrar_pagamento(
            uid, 'asaas', f"ev_{uid}", 10, 'confirmado',
            payload={'origem': 'ativacao_manual'})
        linha = _buscar("SELECT payload->>'origem' FROM pagamentos WHERE user_id = %s", (uid,))
        assert linha[0] == 'ativacao_manual'
    finally:
        _purgar(uid)


# -- Schema ------------------------------------------------------------------

@pytest.mark.parametrize('coluna,default', [
    ('plano_tier', "'trial'"),
    ('plano_status', "'ativo'"),
    ('limite_cabecas', '250'),
])
def test_colunas_de_plano_tem_default(app, coluna, default):
    linha = _buscar(
        "SELECT column_default FROM information_schema.columns "
        "WHERE table_name = 'configuracoes' AND column_name = %s", (coluna,))
    assert linha is not None and default in (linha[0] or '')


def test_trial_ends_at_nao_tem_default(app):
    """Default de coluna teria carimbado a mesma data de vencimento em todas as
    contas que já existiam quando a migration rodou."""
    linha = _buscar(
        "SELECT column_default FROM information_schema.columns "
        "WHERE table_name = 'configuracoes' AND column_name = 'trial_ends_at'")
    assert linha is not None and linha[0] is None
