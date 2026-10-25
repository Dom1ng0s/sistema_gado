"""Mapa de política de acesso por endpoint, com negação por padrão.

Os papéis vêm de `acessos_fazenda`; `dono` é quem não tem linha ativa lá, e
está em todas as tuplas abaixo. O que este módulo compra, além do controle em
si, é o teste `test_todo_endpoint_tem_politica`: rota nova sem política
declarada deixa a suíte vermelha, em vez de nascer aberta e ninguém notar.

Os papéis previstos:

- `dono`      — quem criou a conta. Vende, exclui, mexe em dinheiro e configuração.
- `vaqueiro`  — operação de campo: cadastro, pesagem, medicação, pasto, estoque.
- `contador`  — só os números financeiros, e só leitura.
- `consultor` — leitura ampla para análise, sem escrever nada na fazenda.
"""

import logging

from flask import abort, request
from flask_login import current_user

log = logging.getLogger(__name__)

SAFE = {'GET', 'HEAD', 'OPTIONS'}

#: Papéis que nunca escrevem na fazenda. A barreira é o método HTTP, não a
#: ausência do endpoint no mapa: um GET novo num endpoint de dinheiro continua
#: liberado para o contador, e um POST novo não.
SOMENTE_LEITURA = frozenset({'contador', 'consultor'})

#: Exceções ao bloqueio acima: POSTs que não alteram dado da fazenda.
NAO_ESCREVE_NA_FAZENDA = frozenset({
    'api.auth_logout',
    'api.auth_trocar_fazenda',
})

PAPEIS = ('dono', 'vaqueiro', 'contador', 'consultor')

TODOS = ('dono', 'vaqueiro', 'contador', 'consultor')
GESTAO = ('dono',)
CAMPO = ('dono', 'vaqueiro')
CAMPO_LEITURA = ('dono', 'vaqueiro', 'consultor')
DINHEIRO = ('dono', 'contador', 'consultor')

#: Endpoints que respondem sem sessão. Tudo que não está aqui nem em POLICY é 403.
PUBLICO = frozenset({
    # Máquina, não pessoa: quem autentica é o token do provider.
    'webhooks.asaas',
    # Autenticação de sessão JSON.
    'api.auth_login',
})

POLICY = {
    # --- API: autenticação e sessão ---
    'api.auth_logout':                 TODOS,
    'api.auth_me':                     TODOS,
    'api.auth_trocar_fazenda':         TODOS,

    # --- API: gráficos e export do rebanho ---
    'api.graficos_gmd':                CAMPO_LEITURA,
    'api.graficos_peso':               CAMPO_LEITURA,
    'api.graficos_sexo':               CAMPO_LEITURA,
    'api.gmd_lote':                    CAMPO_LEITURA,
    'api.alerta_gmd':                  CAMPO_LEITURA,
    'api.export_animais_csv':          CAMPO_LEITURA,

    # --- API: rebanho e curral ---
    'api.listar_animais':              CAMPO_LEITURA,
    'api.criar_animal':                CAMPO,
    'api.detalhe_animal':              CAMPO_LEITURA,
    'api.excluir_animal':              GESTAO,
    'api.listar_lixeira':              GESTAO,
    'api.restaurar_lixeira':           GESTAO,
    'api.registrar_pesagens':          CAMPO,
    'api.registrar_medicacoes':        CAMPO,
    'api.registrar_vendas':            GESTAO,

    # --- API: números de dinheiro ---
    'api.dashboard_summary':           DINHEIRO,
    'api.custos_por_ano':              DINHEIRO,
    'api.export_financeiro_csv':       DINHEIRO,
    'api.financeiro_resumo':           DINHEIRO,
    'api.financeiro_resultado_lotes':  DINHEIRO,
    'api.criar_custo':                 GESTAO,
    'api.listar_agendamentos':         DINHEIRO,
    'api.criar_agendamento':           GESTAO,

    # --- API: pastos, sanidade, estoque e reprodução ---
    'api.listar_pastos':               CAMPO_LEITURA,
    'api.listar_protocolos':           CAMPO_LEITURA,
    'api.listar_carencias':            CAMPO_LEITURA,
    'api.listar_estoque':              CAMPO_LEITURA,
    'api.listar_reproducao':           CAMPO_LEITURA,

    # --- API: governança (configurações, acessos, plano) ---
    'api.obter_configuracoes':         GESTAO,
    'api.salvar_configuracoes':        GESTAO,
    'api.listar_acessos':              GESTAO,
    'api.criar_acesso':                GESTAO,
    'api.revogar_acesso':              GESTAO,
    'api.obter_plano':                 GESTAO,

    # --- API: dados de mercado ---
    'api.cotacoes_brasil':             TODOS,
    'api.cotacoes_regionais':          TODOS,
    'api.proxy_cidades':               TODOS,
}


def papel_de(usuario):
    """Papel do usuário logado. Enquanto `acessos_fazenda` não existe, todo
    usuário autenticado é dono da própria conta — é o que mantém este módulo
    inócuo em comportamento."""
    return getattr(usuario, 'papel', 'dono') or 'dono'


def autorizado(endpoint, metodo, papel):
    """True se `papel` pode chamar `endpoint` com `metodo`.

    Função pura de propósito: é o que os testes exercitam sem subir request.
    Endpoint não declarado é negado — o default-deny vive aqui.
    """
    if endpoint in PUBLICO:
        return True
    papeis = POLICY.get(endpoint)
    if papeis is None:
        return False
    if papel not in papeis:
        return False
    if (papel in SOMENTE_LEITURA
            and metodo not in SAFE
            and endpoint not in NAO_ESCREVE_NA_FAZENDA):
        return False
    return True


def checar_politica():
    """`before_request` que nega por padrão.

    Requisição sem sessão passa batido de propósito: quem responde é o
    `login_required` do endpoint, que devolve 401 em vez de 403 — a distinção
    entre "não sei quem você é" e "sei, e você não pode" é o que o cliente da
    API precisa para saber se vale reautenticar.
    """
    endpoint = request.endpoint
    if endpoint is None:          # URL inexistente: deixa o 404 do Flask responder
        return None
    if endpoint in PUBLICO:
        return None

    if endpoint not in POLICY:
        log.error("Endpoint sem política declarada: %s (%s %s) — negado",
                  endpoint, request.method, request.path)
        abort(403)

    if not current_user.is_authenticated:
        return None

    papel = papel_de(current_user)
    if not autorizado(endpoint, request.method, papel):
        log.warning("Acesso negado: papel=%s endpoint=%s metodo=%s user=%s",
                    papel, endpoint, request.method, current_user.get_id())
        abort(403)
    return None


def registrar_politica(app):
    app.before_request(checar_politica)
