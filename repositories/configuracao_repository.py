from db_config import get_db_cursor


def get_configuracao(user_id):
    """Retorna (nome_fazenda, cidade_estado, area_total, gmd_meta) ou None se não configurado."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT nome_fazenda, cidade_estado, area_total, gmd_meta "
            "FROM configuracoes WHERE user_id = %s",
            (user_id,)
        )
        return cursor.fetchone()


def upsert_configuracao(user_id, nome_fazenda, cidade_estado, area_total, gmd_meta=0.800):
    """Cria ou atualiza as configurações do usuário (INSERT … ON CONFLICT DO UPDATE)."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO configuracoes (user_id, nome_fazenda, cidade_estado, area_total, gmd_meta) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (user_id) DO UPDATE SET "
            "nome_fazenda = EXCLUDED.nome_fazenda, "
            "cidade_estado = EXCLUDED.cidade_estado, "
            "area_total = EXCLUDED.area_total, "
            "gmd_meta = EXCLUDED.gmd_meta",
            (user_id, nome_fazenda, cidade_estado, area_total, gmd_meta)
        )


def get_plano(user_id):
    """Plano da fazenda como dicionário, com os padrões de `utils.plano`.

    Nunca devolve None: conta sem linha em `configuracoes` cai em PLANO_PADRAO.
    Quem chama é o `before_request` — levantar aqui derrubaria o app inteiro por
    causa de uma linha faltando.
    """
    from utils.plano import PLANO_PADRAO

    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT plano_tier, plano_status, trial_ends_at, limite_cabecas "
            "FROM configuracoes WHERE user_id = %s",
            (user_id,)
        )
        linha = cursor.fetchone()
    if not linha:
        return dict(PLANO_PADRAO)
    return {
        'tier': linha[0],
        'status': linha[1],
        'trial_ends_at': linha[2],
        'limite_cabecas': linha[3],
    }


def ativar_plano(user_id, tier, limite_cabecas, status='ativo'):
    """Aplica o plano pago. Encerra o trial (`trial_ends_at = NULL`) porque ele
    deixa de ser a resposta para "até quando esta conta vale".

    Chamada pela ativação manual (scripts/ativar_plano.py) enquanto não há
    webhook. Retorna False se a conta não tem linha de configuração — o
    operador precisa saber que nada foi aplicado.
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            "UPDATE configuracoes SET plano_tier = %s, plano_status = %s, "
            "limite_cabecas = %s, trial_ends_at = NULL WHERE user_id = %s",
            (tier, status, limite_cabecas, user_id)
        )
        return cursor.rowcount > 0


def registrar_pagamento(user_id, provider, provider_event_id, valor, status,
                        payload=None):
    """Grava o pagamento e devolve True se era novo.

    O ON CONFLICT DO NOTHING sobre UNIQUE (provider, provider_event_id) é o que
    torna a operação idempotente: hoje impede o operador de ativar duas vezes a
    mesma cobrança; quando o webhook existir, engole o reenvio do provider.
    """
    import json

    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO pagamentos (user_id, provider, provider_event_id, valor, "
            "status, payload) VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (provider, provider_event_id) DO NOTHING",
            (user_id, provider, provider_event_id, valor, status,
             json.dumps(payload) if payload is not None else None)
        )
        return cursor.rowcount > 0
