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

#: Exceções ao bloqueio acima: POSTs que não alteram dado da fazenda. Relatório
#: e simulador são leitura que só vem por POST (payload grande); apagar a conta é
#: ato de identidade — mexe na linha do próprio usuário, não no rebanho.
NAO_ESCREVE_NA_FAZENDA = frozenset({
    'api.relatorio_pdf',
    'financeiro.simulador_custo',
    'auth.apagar_conta',
    'auth.trocar_fazenda',
})

PAPEIS = ('dono', 'vaqueiro', 'contador', 'consultor')

TODOS = ('dono', 'vaqueiro', 'contador', 'consultor')
GESTAO = ('dono',)
CAMPO = ('dono', 'vaqueiro')
CAMPO_LEITURA = ('dono', 'vaqueiro', 'consultor')
DINHEIRO = ('dono', 'contador', 'consultor')

#: Endpoints que respondem sem sessão. Tudo que não está aqui nem em POLICY é 403.
PUBLICO = frozenset({
    'index',
    'static',
    'robots_txt',
    'sitemap_xml',
    'llms_txt',
    'styleguide',
    'auth.login',
    'auth.novo_usuario',
    'auth.esqueci_senha',
    'auth.nova_senha',
    'auth.verificar_codigo',
    'auth.reenviar_codigo',
})

POLICY = {
    # --- identidade ---
    'auth.logout':                     TODOS,
    'auth.apagar_conta':               TODOS,
    'auth.trocar_fazenda':             TODOS,

    # --- rebanho: leitura ---
    'operacional.inicio':              CAMPO_LEITURA,
    'operacional.painel':              CAMPO_LEITURA,
    'operacional.detalhes':            CAMPO_LEITURA,
    'operacional.progenie_animal':     CAMPO_LEITURA,
    'operacional.ranking_touros':      CAMPO_LEITURA,
    'operacional.reproducao_painel':   CAMPO_LEITURA,
    'operacional.reproducao_animal':   CAMPO_LEITURA,

    # --- rebanho: operação de campo ---
    'operacional.cadastro':            CAMPO,
    'operacional.cadastro_lote':       CAMPO,
    'operacional.nova_pesagem':        CAMPO,
    'operacional.pesagem_lote':        CAMPO,
    'operacional.medicar':             CAMPO,
    'operacional.vacinacao_coletiva':  CAMPO,
    'operacional.registrar_reproducao': CAMPO,
    'operacional.registrar_diagnostico': CAMPO,

    # --- rebanho: saída, exclusão e importação são do dono ---
    'operacional.vender':              GESTAO,
    'operacional.venda_lote':          GESTAO,
    'operacional.excluir_animal':      GESTAO,
    'operacional.excluir_pesagem':     GESTAO,
    'operacional.restaurar_animal':    GESTAO,
    'operacional.lixeira':             GESTAO,
    'operacional.importar_csv':        GESTAO,

    # --- pastos ---
    'pastos.listar_pastos':            CAMPO_LEITURA,
    'pastos.detalhe_pasto':            CAMPO_LEITURA,
    'pastos.gmd_por_modulo':           CAMPO_LEITURA,
    'pastos.criar_pasto':              CAMPO,
    'pastos.criar_modulo':             CAMPO,
    'pastos.ocupar_modulo':            CAMPO,
    'pastos.encerrar_ocupacao':        CAMPO,

    # --- estoque (a lista também cadastra produto via POST) ---
    'estoque.lista_estoque':           CAMPO_LEITURA,
    'estoque.detalhe_estoque':         CAMPO_LEITURA,
    'estoque.registrar_entrada':       CAMPO,
    'estoque.registrar_saida':         CAMPO,

    # --- sanitário (a lista também cria protocolo via POST) ---
    'sanitario.lista_protocolos':      CAMPO_LEITURA,
    'sanitario.aplicar_protocolo':     CAMPO,
    'sanitario.desativar_protocolo':   CAMPO,

    # --- financeiro: leitura é do contador; escrita, do dono ---
    'financeiro.financeiro':           DINHEIRO,
    'financeiro.resultado_lotes':      DINHEIRO,
    'financeiro.detalhe_lote':         DINHEIRO,
    'financeiro.simulador_custo':      DINHEIRO,
    'financeiro.agendamentos':         DINHEIRO,
    'financeiro.custos_operacionais':  DINHEIRO,
    'financeiro.baixar_agendamento':   GESTAO,
    'financeiro.editar_agendamento':   GESTAO,
    'financeiro.excluir_agendamento':  GESTAO,

    # --- API: gráficos e export do rebanho ---
    'api.graficos_page':               CAMPO_LEITURA,
    'api.graficos_gmd':                CAMPO_LEITURA,
    'api.graficos_peso':               CAMPO_LEITURA,
    'api.graficos_sexo':               CAMPO_LEITURA,
    'api.gmd_lote':                    CAMPO_LEITURA,
    'api.alerta_gmd':                  CAMPO_LEITURA,
    'api.export_animais_csv':          CAMPO_LEITURA,

    # --- API: números de dinheiro ---
    'api.dashboard_summary':           DINHEIRO,
    'api.custos_por_ano':              DINHEIRO,
    'api.export_financeiro_csv':       DINHEIRO,

    # --- API: relatório e dados de mercado ---
    'api.relatorio_pdf':               TODOS,
    'api.pdf_status':                  TODOS,
    'api.pdf_download':                TODOS,
    'api.cotacoes_brasil':             TODOS,
    'api.cotacoes_regionais':          TODOS,
    'api.proxy_cidades':               TODOS,

    # --- configuração da fazenda ---
    'configuracoes.settings':          GESTAO,
    'configuracoes.plano':             GESTAO,
    'configuracoes.acessos':           GESTAO,
    'configuracoes.revogar_acesso':    GESTAO,
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
    `login_required` do endpoint, que redireciona para o login em vez de
    devolver 403 — trocar isso mudaria o comportamento de toda tela protegida.
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
