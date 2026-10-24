#!/usr/bin/env python3
"""Ativação manual de plano, depois de conferir o pagamento no Asaas.

Enquanto não existe webhook (PR 4b), este script é a ativação: o dono paga pelo
link, o pagamento é conferido no painel do provider, e aqui o plano é aplicado.
O id da cobrança é obrigatório porque é ele que torna a operação idempotente —
o UNIQUE (provider, provider_event_id) em `pagamentos` recusa a segunda
ativação da mesma cobrança, que é o erro de operação mais fácil de cometer.

Rodar:
    python scripts/ativar_plano.py --conta joao --tier porteira --limite 250 \
        --cobranca pay_8392012 --valor 149.90

Sem limite (conta negociada à mão):
    python scripts/ativar_plano.py --conta joao --tier sede --limite 0 --cobranca pay_x
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_config import get_db_cursor                       # noqa: E402
from repositories import configuracao_repository          # noqa: E402


def resolver_conta(conta):
    """id do usuário a partir do id, username ou email."""
    with get_db_cursor() as cursor:
        if conta.isdigit():
            cursor.execute("SELECT id, username FROM usuarios WHERE id = %s", (int(conta),))
        else:
            cursor.execute(
                "SELECT id, username FROM usuarios WHERE username = %s OR email = %s",
                (conta, conta.lower()),
            )
        return cursor.fetchone()


def main():
    p = argparse.ArgumentParser(description="Ativa o plano pago de uma fazenda.")
    p.add_argument('--conta', required=True, help="id, username ou email do DONO da fazenda")
    p.add_argument('--tier', required=True, help="nome do plano, ex.: porteira")
    p.add_argument('--limite', required=True, type=int,
                   help="limite de cabeças; 0 ou negativo = sem limite")
    p.add_argument('--cobranca', required=True, help="id da cobrança no provider")
    p.add_argument('--valor', type=float, default=None, help="valor pago")
    p.add_argument('--provider', default='asaas')
    args = p.parse_args()

    linha = resolver_conta(args.conta)
    if not linha:
        print(f"Conta não encontrada: {args.conta}")
        return 1
    user_id, username = linha

    novo = configuracao_repository.registrar_pagamento(
        user_id, args.provider, args.cobranca, args.valor, 'confirmado',
        payload={'origem': 'ativacao_manual', 'tier': args.tier, 'limite': args.limite},
    )
    if not novo:
        print(f"A cobrança {args.provider}:{args.cobranca} já foi usada em uma "
              f"ativação. Nada alterado.")
        return 1

    if not configuracao_repository.ativar_plano(user_id, args.tier, args.limite):
        # O pagamento fica registrado de propósito: ele aconteceu. O que falta é
        # a linha de configuração, que o cadastro cria — conta antiga pode não ter.
        print(f"A conta {username} (id {user_id}) não tem linha em `configuracoes`; "
              f"o pagamento foi registrado, mas o plano NÃO foi aplicado.")
        return 1

    limite = 'sem limite' if args.limite <= 0 else f"{args.limite} cabeças"
    print(f"Plano de {username} (id {user_id}): {args.tier}, {limite}. Trial encerrado.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
