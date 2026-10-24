"""Webhook de pagamento (Asaas).

Endpoint de escrita sem sessão — por isso as três guardas que ele tem:

1. `csrf.exempt` no registro (app.py). Sem isso, todo POST do provider levaria
   400 do CSRFProtect global e o webhook nunca funcionaria.
2. Token no header `asaas-access-token`, comparado com `hmac.compare_digest`.
   Comparação com `==` vaza o prefixo pelo tempo de resposta, e um webhook sem
   verificação é um endpoint de escrita aberto na internet.
3. Sem token configurado o endpoint responde 503 e não grava nada. Falha
   fechado: ligar o webhook antes de configurar o segredo não pode deixar a
   porta destrancada.

Idempotência não é opcional: o provider reenvia o mesmo evento até receber 200.
Quem garante é o UNIQUE (provider, provider_event_id) em `pagamentos` — a
segunda entrega grava zero linhas e responde 200 do mesmo jeito.

O que este endpoint decide é só se o pagamento entrou ou parou de entrar. O
tamanho do plano (tier e limite) continua sendo de quem vende — ver
`scripts/ativar_plano.py`.
"""

import hmac
import logging
import os

from flask import Blueprint, request, jsonify

from extensions import limiter
from repositories import auth_repository, configuracao_repository

webhooks_bp = Blueprint('webhooks', __name__)
logger = logging.getLogger(__name__)

PROVIDER = 'asaas'

#: Eventos que confirmam dinheiro entrando.
EVENTOS_CONFIRMA = {'PAYMENT_CONFIRMED', 'PAYMENT_RECEIVED'}

#: Eventos que dizem que o dinheiro não entrou (ou voltou). Não apagam nada:
#: mudam o status, e o limite de cabeças continua valendo pelo que está em
#: `configuracoes`.
EVENTOS_INADIMPLENCIA = {
    'PAYMENT_OVERDUE', 'PAYMENT_REFUNDED', 'PAYMENT_DELETED',
    'PAYMENT_CHARGEBACK_REQUESTED', 'PAYMENT_CHARGEBACK_DISPUTE',
    'PAYMENT_REVERSED',
}


def _token_configurado():
    return os.getenv('ASAAS_WEBHOOK_TOKEN', '')


def _token_confere(recebido):
    esperado = _token_configurado()
    if not esperado or not recebido:
        return False
    return hmac.compare_digest(str(recebido), str(esperado))


def resolver_conta(pagamento):
    """user_id dono desta cobrança, ou None.

    Duas pistas, nesta ordem: `externalReference`, que é o campo que o link de
    pagamento carrega quando é criado por conta, e o email do cliente. Nenhuma
    das duas é garantida — cobrança feita por fora chega sem as duas, e é
    exatamente o evento que precisa ficar guardado para a conciliação.
    """
    referencia = (pagamento.get('externalReference') or '').strip()
    if referencia.isdigit():
        return int(referencia)

    email = pagamento.get('email') or ''
    cliente = pagamento.get('customer')
    if isinstance(cliente, dict):
        email = cliente.get('email') or email
    email = (email or '').strip().lower()
    if email:
        conta = auth_repository.get_user_by_email(email)
        if conta:
            return conta[0]
    return None


@webhooks_bp.route('/webhooks/asaas', methods=['POST'])
@limiter.limit("120 per minute")
def asaas():
    if not _token_configurado():
        logger.error("Webhook Asaas chamado sem ASAAS_WEBHOOK_TOKEN configurado.")
        return jsonify({'erro': 'webhook não configurado'}), 503

    if not _token_confere(request.headers.get('asaas-access-token')):
        logger.warning("Webhook Asaas com token inválido (ip=%s)", request.remote_addr)
        return jsonify({'erro': 'token inválido'}), 401

    corpo = request.get_json(silent=True)
    if not isinstance(corpo, dict):
        return jsonify({'erro': 'payload inválido'}), 400

    evento = corpo.get('event') or ''
    pagamento = corpo.get('payment')
    if not isinstance(pagamento, dict) or not pagamento.get('id'):
        return jsonify({'erro': 'evento sem pagamento'}), 400

    user_id = resolver_conta(pagamento)
    confirma = evento in EVENTOS_CONFIRMA
    status = ('confirmado' if confirma
              else 'inadimplente' if evento in EVENTOS_INADIMPLENCIA
              else 'ignorado')

    # O id do evento é o da cobrança mais o evento: a mesma cobrança gera
    # confirmação e, meses depois, estorno — duas linhas, não uma.
    evento_id = f"{pagamento['id']}:{evento}"[:120]

    try:
        novo = configuracao_repository.registrar_pagamento(
            user_id, PROVIDER, evento_id, pagamento.get('value'), status,
            payload=corpo, evento=evento)
    except Exception:
        logger.exception("Falha ao gravar evento %s do Asaas", evento_id)
        # 500 faz o provider reenviar, que é o que queremos: o evento não foi
        # guardado.
        return jsonify({'erro': 'erro interno'}), 500

    if not novo:
        # Reenvio. Já foi processado na primeira entrega.
        return jsonify({'ok': True, 'repetido': True}), 200

    if user_id is None:
        logger.warning("Evento %s sem conta identificada — guardado para conciliação",
                       evento_id)
        return jsonify({'ok': True, 'conciliar': True}), 200

    try:
        if confirma:
            configuracao_repository.encerrar_trial(user_id)
        elif status == 'inadimplente':
            configuracao_repository.marcar_status_plano(user_id, 'inadimplente')
    except Exception:
        # O pagamento já está gravado; o que falhou foi aplicar o efeito. 500
        # não ajuda: o reenvio cairia no UNIQUE e não tentaria de novo.
        logger.exception("Evento %s gravado, mas o plano de %s não foi atualizado",
                         evento_id, user_id)

    return jsonify({'ok': True}), 200
