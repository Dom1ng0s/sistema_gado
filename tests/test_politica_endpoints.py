"""Portão do mapa de política (utils/permissions.py).

O teste que importa é `test_todo_endpoint_tem_politica`: rota nova sem papel
declarado deixa a suíte vermelha. Os demais protegem as invariantes do mapa —
em especial que `dono` continua podendo tudo, que é o que faz este PR ser
inócuo em comportamento enquanto existe um papel só.
"""

import pytest

from utils.permissions import (
    NAO_ESCREVE_NA_FAZENDA,
    PAPEIS,
    POLICY,
    PUBLICO,
    SAFE,
    SOMENTE_LEITURA,
    autorizado,
    papel_de,
)


def _endpoints(app):
    return {r.endpoint for r in app.url_map.iter_rules()}


def test_todo_endpoint_tem_politica(app):
    faltando = sorted(r.endpoint for r in app.url_map.iter_rules()
                      if r.endpoint not in POLICY and r.endpoint not in PUBLICO)
    assert not faltando, f"endpoints sem política declarada: {faltando}"


def test_mapa_nao_tem_endpoint_morto(app):
    """Entrada no mapa para rota que não existe mais é mentira documentada:
    parece coberta e não protege nada."""
    reais = _endpoints(app)
    orfaos = sorted(e for e in set(POLICY) | set(PUBLICO) if e not in reais)
    assert not orfaos, f"política declarada para endpoints inexistentes: {orfaos}"


def test_publico_e_policy_sao_disjuntos():
    assert not (set(POLICY) & PUBLICO)


def test_papeis_declarados_existem():
    invalidos = {e: p for e, p in POLICY.items()
                 if not p or any(papel not in PAPEIS for papel in p)}
    assert not invalidos, f"papéis desconhecidos ou tupla vazia: {invalidos}"


def test_dono_pode_tudo():
    """A garantia de que o PR não muda comportamento: hoje todo usuário
    autenticado é dono."""
    negados = [e for e in POLICY if 'dono' not in POLICY[e]]
    assert not negados, f"dono barrado em: {negados}"


def test_endpoint_desconhecido_e_negado():
    for papel in PAPEIS:
        assert not autorizado('blueprint.rota_que_nao_existe', 'GET', papel)


def test_publico_passa_sem_papel():
    assert autorizado('auth.login', 'POST', 'anonimo')
    assert autorizado('static', 'GET', 'anonimo')


def test_papel_desconhecido_e_negado():
    assert not autorizado('operacional.painel', 'GET', 'invasor')


# ---- recortes de papel ----

def test_vaqueiro_opera_campo_mas_nao_vende():
    assert autorizado('operacional.medicar', 'POST', 'vaqueiro')
    assert autorizado('operacional.pesagem_lote', 'POST', 'vaqueiro')
    assert not autorizado('operacional.vender', 'POST', 'vaqueiro')
    assert not autorizado('operacional.venda_lote', 'POST', 'vaqueiro')
    assert not autorizado('operacional.excluir_animal', 'POST', 'vaqueiro')


def test_vaqueiro_nao_ve_dinheiro():
    for endpoint in ('financeiro.financeiro', 'financeiro.resultado_lotes',
                     'api.dashboard_summary', 'api.export_financeiro_csv',
                     'configuracoes.settings'):
        assert not autorizado(endpoint, 'GET', 'vaqueiro'), endpoint


def test_contador_le_dinheiro_e_nao_escreve():
    assert autorizado('financeiro.financeiro', 'GET', 'contador')
    assert autorizado('api.export_financeiro_csv', 'GET', 'contador')
    # mesmo endpoint, método que grava: barrado pelo método, não pelo mapa
    assert autorizado('financeiro.custos_operacionais', 'GET', 'contador')
    assert not autorizado('financeiro.custos_operacionais', 'POST', 'contador')
    assert not autorizado('financeiro.agendamentos', 'POST', 'contador')


def test_contador_nao_entra_no_rebanho():
    assert not autorizado('operacional.painel', 'GET', 'contador')
    assert not autorizado('operacional.detalhes', 'GET', 'contador')


def test_consultor_le_mas_nao_grava():
    assert autorizado('operacional.painel', 'GET', 'consultor')
    assert autorizado('estoque.lista_estoque', 'GET', 'consultor')
    assert not autorizado('estoque.lista_estoque', 'POST', 'consultor')
    assert not autorizado('sanitario.lista_protocolos', 'POST', 'consultor')


@pytest.mark.parametrize('endpoint', sorted(NAO_ESCREVE_NA_FAZENDA))
def test_excecoes_de_post_valem_para_leitores(endpoint):
    """POST que não altera dado da fazenda (relatório, simulador, apagar a
    própria conta) continua liberado para quem é só leitura."""
    for papel in sorted(SOMENTE_LEITURA):
        if papel in POLICY[endpoint]:
            assert autorizado(endpoint, 'POST', papel), (endpoint, papel)


def test_metodos_de_escrita_sao_barrados_em_todo_endpoint_de_leitor():
    """Varredura: para cada endpoint onde um papel só-leitura aparece, um POST
    tem de cair — exceto as exceções declaradas."""
    for endpoint, papeis in POLICY.items():
        if endpoint in NAO_ESCREVE_NA_FAZENDA:
            continue
        for papel in papeis:
            if papel in SOMENTE_LEITURA:
                assert not autorizado(endpoint, 'POST', papel), (endpoint, papel)


def test_metodos_safe_sao_os_tres():
    assert SAFE == {'GET', 'HEAD', 'OPTIONS'}


# ---- integração: o before_request está de pé e é inócuo ----

def test_hook_esta_registrado(app):
    nomes = [f.__name__ for f in app.before_request_funcs.get(None, [])]
    assert 'checar_politica' in nomes


def test_usuario_sem_papel_e_dono():
    class _U:
        pass
    assert papel_de(_U()) == 'dono'
    assert papel_de(None) == 'dono'


def test_telas_protegidas_continuam_redirecionando_para_login(client):
    """Sem sessão o hook não responde 403: quem responde é o login_required."""
    resp = client.get('/painel')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_usuario_logado_passa_pelo_hook(client, app):
    client.post('/login', data={'username': 'testuser', 'password': '123'},
                follow_redirects=True)
    for url in ('/inicio', '/painel', '/financeiro', '/configuracoes'):
        assert client.get(url).status_code == 200, url


def test_rota_inexistente_ainda_da_404(client):
    assert client.get('/rota-que-nao-existe').status_code == 404
