"""Webhook de pagamento: autenticação, idempotência e conciliação.

Três testes carregam o PR. `test_sem_token_configurado_nao_grava_nada` é a
falha fechada: ligar o webhook antes de configurar o segredo não pode deixar um
endpoint de escrita aberto na internet. `test_reenvio_nao_duplica` é o UNIQUE
fazendo o trabalho — o provider reenvia até receber 200.
`test_evento_sem_conta_fica_guardado` é a conciliação: o evento que não acha
dono é justamente o que precisa sobrar para alguém procurar.
"""
import itertools
import json

import pytest
from werkzeug.security import generate_password_hash

from repositories import configuracao_repository
from tests.dbcompat import connect

_seq = itertools.count(19000)

TOKEN = 'segredo-de-teste-123'
URL = '/webhooks/asaas'


@pytest.fixture(autouse=True)
def token_configurado(monkeypatch):
    monkeypatch.setenv('ASAAS_WEBHOOK_TOKEN', TOKEN)


# -- Helpers -----------------------------------------------------------------

def _criar_dono(email=None, tier='trial', dias_trial=10):
    n = next(_seq)
    username = f"wh_{n}"
    email = email or f"{username}@exemplo.com"
    conn = connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO usuarios (username, password_hash, email) VALUES (%s, %s, %s)",
                (username, generate_password_hash("senha123"), email))
    uid = cur.lastrowid
    cur.execute(
        "INSERT INTO configuracoes (user_id, nome_fazenda, plano_tier, trial_ends_at) "
        "VALUES (%s, %s, %s, now() + make_interval(days => %s))",
        (uid, f"Fazenda {n}", tier, dias_trial))
    conn.commit()
    cur.close()
    conn.close()
    return uid, email


def _buscar(sql, params=()):
    conn = connect()
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def _purgar(user_id=None, evento_like='pay_%'):
    conn = connect()
    cur = conn.cursor()
    cur.execute("SET session_replication_role = 'replica'")
    cur.execute("DELETE FROM pagamentos WHERE provider_event_id LIKE %s", (evento_like,))
    if user_id:
        cur.execute("DELETE FROM pagamentos WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM configuracoes WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM usuarios WHERE id = %s", (user_id,))
    cur.execute("SET session_replication_role = 'origin'")
    conn.commit()
    cur.close()
    conn.close()


def _evento(cobranca, event='PAYMENT_CONFIRMED', valor=149.90, **pagamento):
    corpo = {'event': event, 'payment': {'id': cobranca, 'value': valor}}
    corpo['payment'].update(pagamento)
    return corpo


def _postar(client, corpo, token=TOKEN):
    headers = {'Content-Type': 'application/json'}
    if token is not None:
        headers['asaas-access-token'] = token
    return client.post(URL, data=json.dumps(corpo), headers=headers)


# -- Autenticação ------------------------------------------------------------

def test_sem_token_no_header_e_401(client):
    resp = _postar(client, _evento('pay_x1'), token=None)
    assert resp.status_code == 401
    assert _buscar("SELECT COUNT(*) FROM pagamentos "
                    "WHERE provider_event_id LIKE %s", ('pay_x1%',))[0] == 0


def test_token_errado_e_401(client):
    resp = _postar(client, _evento('pay_x2'), token='quase-o-token')
    assert resp.status_code == 401


def test_sem_token_configurado_nao_grava_nada(client, monkeypatch):
    """Falha fechada: webhook ligado antes do segredo não pode gravar."""
    monkeypatch.setenv('ASAAS_WEBHOOK_TOKEN', '')
    resp = _postar(client, _evento('pay_x3'), token='qualquer')
    assert resp.status_code == 503
    assert _buscar("SELECT COUNT(*) FROM pagamentos "
                    "WHERE provider_event_id LIKE %s", ('pay_x3%',))[0] == 0


def test_o_webhook_esta_fora_do_csrf(app, client):
    """Sem o exempt, todo POST do provider levaria 400 do CSRFProtect e o
    endpoint nunca funcionaria — inclusive com o token certo."""
    app.config['WTF_CSRF_ENABLED'] = True
    try:
        resp = _postar(client, _evento('pay_csrf'))
        assert resp.status_code != 400
    finally:
        app.config['WTF_CSRF_ENABLED'] = False
        _purgar(evento_like='pay_csrf%')


# -- Payload -----------------------------------------------------------------

def test_payload_que_nao_e_json_e_400(client):
    resp = client.post(URL, data='nao sou json',
                       headers={'asaas-access-token': TOKEN,
                                'Content-Type': 'application/json'})
    assert resp.status_code == 400


def test_evento_sem_pagamento_e_400(client):
    resp = _postar(client, {'event': 'PAYMENT_CONFIRMED'})
    assert resp.status_code == 400


# -- Efeito no plano ---------------------------------------------------------

def test_pagamento_confirmado_encerra_o_trial(client):
    uid, _ = _criar_dono()
    try:
        resp = _postar(client, _evento('pay_ok1', externalReference=str(uid)))
        assert resp.status_code == 200
        plano = configuracao_repository.get_plano(uid)
        assert plano['trial_ends_at'] is None
        assert plano['status'] == 'ativo'
        assert plano['tier'] == configuracao_repository.TIER_PAGO_PADRAO
    finally:
        _purgar(uid, 'pay_ok1%')


def test_conta_achada_pelo_email_do_cliente(client):
    uid, email = _criar_dono()
    try:
        _postar(client, _evento('pay_ok2', customer={'email': email.upper()}))
        linha = _buscar("SELECT user_id FROM pagamentos "
                    "WHERE provider_event_id LIKE %s", ('pay_ok2%',))
        assert linha is not None and linha[0] == uid
    finally:
        _purgar(uid, 'pay_ok2%')


def test_atraso_marca_inadimplente_sem_mexer_no_limite(client):
    uid, _ = _criar_dono()
    try:
        _postar(client, _evento('pay_atraso', event='PAYMENT_OVERDUE',
                                externalReference=str(uid)))
        plano = configuracao_repository.get_plano(uid)
        assert plano['status'] == 'inadimplente'
        # O rebanho não some por causa de boleto: o limite continua o que era.
        assert plano['limite_cabecas'] == 250
    finally:
        _purgar(uid, 'pay_atraso%')


def test_estorno_tambem_marca_inadimplente(client):
    uid, _ = _criar_dono()
    try:
        _postar(client, _evento('pay_estorno', event='PAYMENT_REFUNDED',
                                externalReference=str(uid)))
        assert configuracao_repository.get_plano(uid)['status'] == 'inadimplente'
    finally:
        _purgar(uid, 'pay_estorno%')


def test_evento_desconhecido_e_guardado_sem_efeito(client):
    uid, _ = _criar_dono()
    try:
        resp = _postar(client, _evento('pay_outro', event='PAYMENT_CREATED',
                                       externalReference=str(uid)))
        assert resp.status_code == 200
        assert configuracao_repository.get_plano(uid)['status'] == 'ativo'
        linha = _buscar("SELECT status FROM pagamentos "
                    "WHERE provider_event_id LIKE %s", ('pay_outro%',))
        assert linha[0] == 'ignorado'
    finally:
        _purgar(uid, 'pay_outro%')


# -- Idempotência e conciliação ---------------------------------------------

def test_reenvio_nao_duplica(client):
    """O provider reenvia o mesmo evento até receber 200."""
    uid, _ = _criar_dono()
    try:
        corpo = _evento('pay_rep', externalReference=str(uid))
        primeira = _postar(client, corpo)
        segunda = _postar(client, corpo)
        assert primeira.status_code == segunda.status_code == 200
        assert segunda.get_json().get('repetido') is True
        assert _buscar("SELECT COUNT(*) FROM pagamentos "
                    "WHERE provider_event_id LIKE %s", ('pay_rep%',))[0] == 1
    finally:
        _purgar(uid, 'pay_rep%')


def test_confirmacao_e_estorno_da_mesma_cobranca_sao_duas_linhas(client):
    """A mesma cobrança gera confirmação e, meses depois, estorno — se o id do
    evento fosse só o da cobrança, o estorno seria engolido como reenvio."""
    uid, _ = _criar_dono()
    try:
        _postar(client, _evento('pay_dois', externalReference=str(uid)))
        _postar(client, _evento('pay_dois', event='PAYMENT_REFUNDED',
                                externalReference=str(uid)))
        assert _buscar("SELECT COUNT(*) FROM pagamentos "
                    "WHERE provider_event_id LIKE %s", ('pay_dois%',))[0] == 2
        assert configuracao_repository.get_plano(uid)['status'] == 'inadimplente'
    finally:
        _purgar(uid, 'pay_dois%')


def test_evento_sem_conta_fica_guardado(client):
    """Cobrança feita por fora não tem como virar ativação — mas é exatamente
    o evento que a conciliação vai procurar."""
    try:
        resp = _postar(client, _evento('pay_orfao'))
        assert resp.status_code == 200
        assert resp.get_json().get('conciliar') is True
        linha = _buscar("SELECT user_id, valor, evento FROM pagamentos "
                    "WHERE provider_event_id LIKE %s", ('pay_orfao%',))
        assert linha is not None
        assert linha[0] is None
        assert float(linha[1]) == 149.90
        assert linha[2] == 'PAYMENT_CONFIRMED'
    finally:
        _purgar(evento_like='pay_orfao%')


def test_payload_cru_fica_gravado(client):
    """Quando a conciliação não fechar, é a única fonte do que o provider
    realmente mandou."""
    try:
        _postar(client, _evento('pay_cru', billingType='PIX'))
        linha = _buscar("SELECT payload->'payment'->>'billingType' FROM pagamentos "
                    "WHERE provider_event_id LIKE %s", ('pay_cru%',))
        assert linha[0] == 'PIX'
    finally:
        _purgar(evento_like='pay_cru%')


def test_referencia_que_nao_e_numero_nao_vira_conta(client):
    """`externalReference` é texto livre no provider: só vale como id se for
    um número, senão viraria acesso à conta errada."""
    try:
        _postar(client, _evento('pay_ref', externalReference='pedido-do-joao'))
        linha = _buscar("SELECT user_id FROM pagamentos "
                    "WHERE provider_event_id LIKE %s", ('pay_ref%',))
        assert linha is not None and linha[0] is None
    finally:
        _purgar(evento_like='pay_ref%')
