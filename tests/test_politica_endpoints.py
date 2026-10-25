"""Portão do mapa de política (utils/permissions.py).

O teste que importa é `test_todo_endpoint_tem_politica`: rota nova sem papel
declarado deixa a suíte vermelha. Os demais protegem as invariantes do mapa —
em especial que `dono` continua podendo tudo, que é o que faz este PR ser
inócuo em comportamento enquanto existe um papel só.
"""

import pytest

from conftest import login_as
from tests.dbcompat import connect
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


def _uid_testuser():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT id FROM usuarios WHERE username = 'testuser'")
    uid = cur.fetchone()[0]
    cur.close(); conn.close()
    return uid


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
    assert autorizado('webhooks.asaas', 'POST', 'anonimo')


def test_papel_desconhecido_e_negado():
    assert not autorizado('api.graficos_sexo', 'GET', 'invasor')


# ---- recortes de papel ----
#
# Encolheram com o HTML: a API que sobrou é toda GET, então o recorte que se
# pode exercitar aqui é quem lê o quê — o barramento por método continua
# coberto pela varredura abaixo.

def test_vaqueiro_le_rebanho():
    assert autorizado('api.graficos_sexo', 'GET', 'vaqueiro')
    assert autorizado('api.alerta_gmd', 'GET', 'vaqueiro')
    assert autorizado('api.export_animais_csv', 'GET', 'vaqueiro')


def test_vaqueiro_nao_ve_dinheiro():
    for endpoint in ('api.dashboard_summary', 'api.custos_por_ano',
                     'api.export_financeiro_csv'):
        assert not autorizado(endpoint, 'GET', 'vaqueiro'), endpoint


def test_contador_le_dinheiro():
    assert autorizado('api.dashboard_summary', 'GET', 'contador')
    assert autorizado('api.export_financeiro_csv', 'GET', 'contador')
    assert autorizado('api.custos_por_ano', 'GET', 'contador')


def test_contador_nao_entra_no_rebanho():
    assert not autorizado('api.graficos_sexo', 'GET', 'contador')
    assert not autorizado('api.export_animais_csv', 'GET', 'contador')


def test_consultor_le_os_dois_lados():
    assert autorizado('api.graficos_sexo', 'GET', 'consultor')
    assert autorizado('api.dashboard_summary', 'GET', 'consultor')


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


def test_rota_protegida_sem_sessao_da_401(client):
    """Sem sessão o hook não responde 403: quem responde é o login_required,
    que agora devolve 401 — não há mais tela de login para onde redirecionar."""
    resp = client.get('/api/graficos/sexo')
    assert resp.status_code == 401


def test_usuario_logado_passa_pelo_hook(client, app):
    uid = _uid_testuser()
    login_as(client, uid)
    for url in ('/api/graficos/sexo', '/api/graficos/gmd', '/api/dashboard-summary'):
        assert client.get(url).status_code == 200, url


def test_rota_inexistente_ainda_da_404(client):
    assert client.get('/rota-que-nao-existe').status_code == 404
