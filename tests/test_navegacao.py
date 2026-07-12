"""
Testes da navegação global (base.html).

Guardam as invariantes das issues #68/#69/#71: cada módulo entregue precisa ter
uma porta estável na navbar, e não pode haver página cuja única entrada seja um
widget condicional (o bug circular do Sanitário) ou um hub redundante.
"""
import pytest


def login(client):
    return client.post('/login', data={'username': 'testuser', 'password': '123'},
                       follow_redirects=True)


# Páginas internas representativas — a navbar é a mesma em todas (base.html).
PAGINAS = ['/painel', '/financeiro', '/estoque', '/pastos', '/graficos']


@pytest.mark.parametrize('pagina', PAGINAS)
def test_navbar_expoe_sanitario_em_qualquer_pagina(client, pagina):
    """#68: /sanitario precisa estar na navbar, não só num widget de alerta condicional.

    Antes, a única porta estável era um link dentro do Estoque — e o widget do
    painel só renderizava se já existisse protocolo vencendo, o que tornava
    impossível criar o primeiro protocolo.
    """
    login(client)
    r = client.get(pagina)
    assert r.status_code == 200
    assert b'/sanitario' in r.data


@pytest.mark.parametrize('pagina', PAGINAS)
def test_navbar_expoe_reproducao_em_qualquer_pagina(client, pagina):
    """#70: reprodução precisa de entrada de primeiro nível, não só via ficha do animal."""
    login(client)
    r = client.get(pagina)
    assert r.status_code == 200
    assert b'href="/reproducao"' in r.data


def test_rota_transacoes_nao_existe_mais(client):
    """#69: o hub /transacoes duplicava o dropdown "+ Novo" e foi removido."""
    login(client)
    assert client.get('/transacoes').status_code == 404


def test_painel_nao_linka_ranking_touros(client):
    """#71: o ranking tinha 3 entradas espalhadas; agora só vive em Relatórios."""
    login(client)
    r = client.get('/painel')
    assert r.status_code == 200
    assert b'/rebanho/ranking-touros' not in r.data

    # A entrada canônica continua em Relatórios.
    r = client.get('/graficos')
    assert r.status_code == 200
    assert b'/rebanho/ranking-touros' in r.data


def test_relatorios_agrupa_ranking_e_gmd_por_modulo(client):
    """#71: ranking de touros e GMD por módulo são análise, não finanças."""
    login(client)
    r = client.get('/graficos')
    assert r.status_code == 200
    assert b'/pastos/gmd' in r.data
