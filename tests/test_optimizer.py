"""
Testes de regressão para as otimizações do Optimizer Plan.
Cada teste verifica o comportamento CORRETO esperado após a correção.
"""
import itertools
import threading
import time
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

import pytest
from werkzeug.security import generate_password_hash

import db_config as dbc
from repositories import animal_repository, financeiro_repository

_seq = itertools.count(9000)


def _n():
    return next(_seq)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_user():
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
        (f"opt_u{_n()}", generate_password_hash("x")),
    )
    uid = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return uid


def _make_animal(user_id, brinco=None, sexo="M", preco=1000.0, vendido=False):
    brinco = brinco or f"OPT{_n()}"
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id)"
        " VALUES (%s, %s, '2024-01-01', %s, %s)",
        (brinco, sexo, preco, user_id),
    )
    aid = cur.lastrowid
    if vendido:
        cur.execute(
            "UPDATE animais SET data_venda='2024-12-01', preco_venda=2000 WHERE id=%s",
            (aid,)
        )
    conn.commit()
    cur.close()
    conn.close()
    return aid, brinco


def _add_pesagem(animal_id, data_str, peso):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)",
        (animal_id, data_str, peso),
    )
    conn.commit()
    cur.close()
    conn.close()


def _add_medicacao(animal_id, data_str, nome, custo=50.0):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO medicacoes (animal_id, data_aplicacao, nome_medicamento, custo)"
        " VALUES (%s, %s, %s, %s)",
        (animal_id, data_str, nome, custo),
    )
    conn.commit()
    cur.close()
    conn.close()


def _count_medicacoes(animal_id):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM medicacoes WHERE animal_id=%s", (animal_id,))
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count


def _count_pesagens(animal_id):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM pesagens WHERE animal_id=%s AND deleted_at IS NULL",
        (animal_id,)
    )
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count


# ══════════════════════════════════════════════════════════════════════════════
# H4 — Batch INSERTs: insert_medicacao_lote e registrar_pesagens_lote
# ══════════════════════════════════════════════════════════════════════════════

class TestBatchInserts:
    """H4 — Verificar que batch operations inserem todos os registros corretamente."""

    def test_insert_medicacao_lote_insere_todos_os_animais(self, app):
        uid = _make_user()
        aids = [_make_animal(uid)[0] for _ in range(5)]

        animal_repository.insert_medicacao_lote(
            aids, "2024-06-01", "Ivermectina", 45.00, "Dose preventiva"
        )

        for aid in aids:
            assert _count_medicacoes(aid) == 1, (
                f"Animal {aid} deveria ter 1 medicação, mas tem {_count_medicacoes(aid)}"
            )

    def test_insert_medicacao_lote_com_um_animal(self, app):
        uid = _make_user()
        aid, _ = _make_animal(uid)

        animal_repository.insert_medicacao_lote([aid], "2024-07-01", "Vermífugo", 30.0, "")

        assert _count_medicacoes(aid) == 1

    def test_insert_medicacao_lote_vazio_nao_explode(self, app):
        """Lista vazia não deve lançar exceção."""
        animal_repository.insert_medicacao_lote([], "2024-07-01", "Teste", 10.0, "")

    def test_registrar_pesagens_lote_insere_todos_os_pares_validos(self, app):
        uid = _make_user()
        aids = [_make_animal(uid)[0] for _ in range(3)]
        data = "2024-08-01"

        pairs = [(aid, 350.0 + i * 10) for i, aid in enumerate(aids)]
        inseridos, invalidos = animal_repository.registrar_pesagens_lote(pairs, uid, data)

        assert inseridos == 3
        assert invalidos == []
        for aid in aids:
            assert _count_pesagens(aid) == 1, (
                f"Animal {aid} deveria ter 1 pesagem mas tem {_count_pesagens(aid)}"
            )

    def test_registrar_pesagens_lote_rejeita_animais_de_outro_usuario(self, app):
        uid_a = _make_user()
        uid_b = _make_user()
        aid_a, _ = _make_animal(uid_a)
        aid_b, _ = _make_animal(uid_b)

        pairs = [(aid_a, 300.0), (aid_b, 400.0)]
        inseridos, invalidos = animal_repository.registrar_pesagens_lote(pairs, uid_a, "2024-09-01")

        assert inseridos == 1
        assert aid_b in invalidos

    def test_registrar_pesagens_lote_vazio_retorna_zero(self, app):
        uid = _make_user()
        inseridos, invalidos = animal_repository.registrar_pesagens_lote([], uid, "2024-09-01")
        assert inseridos == 0
        assert invalidos == []


# ══════════════════════════════════════════════════════════════════════════════
# L3 — get_medicacoes_by_animal: ORDER BY data_aplicacao DESC
# ══════════════════════════════════════════════════════════════════════════════

class TestMedicacoesOrdenadas:
    """L3 — Medicações devem vir em ordem decrescente de data."""

    def test_medicacoes_retornam_mais_recente_primeiro(self, app):
        uid = _make_user()
        aid, _ = _make_animal(uid)

        _add_medicacao(aid, "2024-01-10", "Med Antigo", 20.0)
        _add_medicacao(aid, "2024-09-15", "Med Recente", 60.0)
        _add_medicacao(aid, "2024-05-20", "Med Meio", 40.0)

        meds = animal_repository.get_medicacoes_by_animal(aid)

        assert len(meds) == 3
        datas = [str(m[2]) for m in meds]  # coluna data_aplicacao (índice 2)
        assert datas == sorted(datas, reverse=True), (
            f"Medicações não estão em ordem decrescente: {datas}"
        )

    def test_medicacoes_vazio_retorna_lista_vazia(self, app):
        uid = _make_user()
        aid, _ = _make_animal(uid)
        meds = animal_repository.get_medicacoes_by_animal(aid)
        assert meds == []


# ══════════════════════════════════════════════════════════════════════════════
# H3 — get_animais_com_gmd: sem dependência de v_gmd_analitico
# ══════════════════════════════════════════════════════════════════════════════

class TestAnimaisComGmd:
    """H3 — get_animais_com_gmd deve calcular GMD inline sem usar v_gmd_analitico."""

    def test_retorna_gmd_calculado_corretamente(self, app):
        uid = _make_user()
        aid, brinco = _make_animal(uid)
        _add_pesagem(aid, "2024-01-01", 300.0)
        _add_pesagem(aid, "2024-04-10", 400.0)  # +100kg em 100 dias → GMD=1.0

        rows = animal_repository.get_animais_com_gmd(uid)

        animal_row = next((r for r in rows if r[0] == aid), None)
        assert animal_row is not None, "Animal não encontrado em get_animais_com_gmd"

        # Estrutura: (id, brinco, sexo, raca, data_compra, gmd, dias, peso_final)
        assert len(animal_row) == 8, f"Esperava 8 colunas, got {len(animal_row)}"

        gmd = animal_row[5]
        assert gmd is not None, "GMD deveria ser calculado para animal com 2+ pesagens"
        assert abs(float(gmd) - 1.0) < 0.05, (
            f"GMD esperado ~1.0, calculado {gmd}"
        )

    def test_animal_sem_pesagem_retorna_gmd_none(self, app):
        uid = _make_user()
        aid, brinco = _make_animal(uid)
        # Sem pesagens extras — animal ativo sem histórico de pesagem

        rows = animal_repository.get_animais_com_gmd(uid)

        animal_row = next((r for r in rows if r[0] == aid), None)
        assert animal_row is not None, "Animal sem pesagem deve aparecer (LEFT JOIN)"
        assert animal_row[5] is None, "GMD deve ser None quando não há pesagens suficientes"

    def test_animal_vendido_nao_aparece(self, app):
        uid = _make_user()
        aid_ativo, _ = _make_animal(uid, vendido=False)
        aid_vendido, _ = _make_animal(uid, vendido=True)

        rows = animal_repository.get_animais_com_gmd(uid)
        ids = [r[0] for r in rows]

        assert aid_ativo in ids
        assert aid_vendido not in ids, "Animais vendidos não devem aparecer em get_animais_com_gmd"

    def test_nao_cruza_dados_entre_usuarios(self, app):
        uid_a = _make_user()
        uid_b = _make_user()
        aid_a, _ = _make_animal(uid_a)
        aid_b, _ = _make_animal(uid_b)

        rows_a = animal_repository.get_animais_com_gmd(uid_a)
        ids_a = [r[0] for r in rows_a]

        assert aid_a in ids_a
        assert aid_b not in ids_a, "Multi-tenant: animal de outro usuário não deve aparecer"

    def test_retorna_lista_vazia_para_usuario_sem_animais(self, app):
        uid = _make_user()
        rows = animal_repository.get_animais_com_gmd(uid)
        assert rows == []


# ══════════════════════════════════════════════════════════════════════════════
# H5 — get_categorias_custo: cache em memória
# ══════════════════════════════════════════════════════════════════════════════

class TestCategoriasCustoCache:
    """H5 — get_categorias_custo não deve consultar o banco após o primeiro call."""

    def test_retorna_dados_do_banco(self, app):
        # Limpa cache para garantir leitura fresca
        financeiro_repository._CATEGORIAS_CACHE = None

        rows = financeiro_repository.get_categorias_custo()
        assert len(rows) > 0, "Deve retornar ao menos um cost_center"

    def test_segunda_chamada_usa_cache(self, app):
        """Verifica que o cache é populado e reutilizado."""
        financeiro_repository._CATEGORIAS_CACHE = None

        # Primeira chamada popula o cache
        rows1 = financeiro_repository.get_categorias_custo()
        assert financeiro_repository._CATEGORIAS_CACHE is not None, "Cache deve ser populado"

        # Força o banco a ficar inacessível — segunda chamada deve usar cache
        original_pool = dbc.connection_pool
        dbc.connection_pool = None
        original_settings = dbc.db_settings.copy()
        dbc.db_settings['host'] = 'invalid-host-xyz'

        try:
            rows2 = financeiro_repository.get_categorias_custo()
            assert rows1 == rows2, "Cache deve retornar os mesmos dados"
        finally:
            dbc.connection_pool = original_pool
            dbc.db_settings.update(original_settings)

    def test_cache_e_lista_de_tuplas(self, app):
        financeiro_repository._CATEGORIAS_CACHE = None
        rows = financeiro_repository.get_categorias_custo()
        assert all(isinstance(r, tuple) for r in rows)


# ══════════════════════════════════════════════════════════════════════════════
# L5 — Cotações regionais: mapa_estados completo
# ══════════════════════════════════════════════════════════════════════════════

class TestCotacoesRegionais:
    """L5 — O filtro de cotações deve funcionar para todos os estados brasileiros."""

    def _filtrar(self, uf, dados_boi):
        """Replica a lógica de filtragem de cotacoes_regionais."""
        from routes.api import _MAPA_ESTADOS  # será importado após o fix
        nome_completo = _MAPA_ESTADOS.get(uf, '')

        resultado = []
        for item in dados_boi:
            praca = item.get('praca', '').upper()
            if (praca.startswith(uf) or praca == uf or
                    (nome_completo and praca == nome_completo.upper())):
                resultado.append(item)
        return resultado

    def test_estados_principais_do_agronegocio(self, app):
        """GO, MT, MS, MG, SP — maiores estados pecuários do Brasil."""
        dados_mock = [
            {'praca': 'GOIÂNIA', 'preco_vista': '200.00'},
            {'praca': 'MT - Cuiabá', 'preco_vista': '195.00'},
            {'praca': 'Mato Grosso do Sul', 'preco_vista': '198.00'},
            {'praca': 'Minas Gerais', 'preco_vista': '210.00'},
            {'praca': 'SP - Araçatuba', 'preco_vista': '215.00'},
            {'praca': 'PARÁ', 'preco_vista': '190.00'},
        ]

        # GO: startswith('GO') → 'GOIÂNIA'.startswith('GO') = True
        assert len(self._filtrar('GO', dados_mock)) >= 1

        # SP: startswith('SP') → 'SP - Araçatuba'.startswith('SP') = True
        assert len(self._filtrar('SP', dados_mock)) >= 1

    def test_mapa_estados_cobre_todos_27_estados(self, app):
        """Verifica que _MAPA_ESTADOS está completo."""
        from routes.api import _MAPA_ESTADOS
        ufs_brasil = {
            'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO',
            'MA', 'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI',
            'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO',
        }
        faltando = ufs_brasil - set(_MAPA_ESTADOS.keys())
        assert not faltando, f"Estados faltando no mapa: {faltando}"

    def test_estado_por_nome_completo(self, app):
        """Praças com nome completo do estado devem ser encontradas."""
        from routes.api import _MAPA_ESTADOS
        dados_mock = [
            {'praca': 'MATO GROSSO DO SUL', 'preco_vista': '198.00'},
            {'praca': 'RORAIMA', 'preco_vista': '185.00'},
        ]

        # MS via nome completo
        ms_nome = _MAPA_ESTADOS.get('MS', '').upper()
        ms_result = [i for i in dados_mock if i['praca'] == ms_nome]
        assert len(ms_result) == 1

        # RR via nome completo
        rr_nome = _MAPA_ESTADOS.get('RR', '').upper()
        rr_result = [i for i in dados_mock if i['praca'] == rr_nome]
        assert len(rr_result) == 1


# ══════════════════════════════════════════════════════════════════════════════
# U2 — /proxy-cidades: cache de 24h
# ══════════════════════════════════════════════════════════════════════════════

class TestProxyCidadesCache:
    """U2 — /proxy-cidades deve cachear a resposta do IBGE por 24 horas."""

    def test_segunda_chamada_nao_faz_request_http(self, app):
        """Após o primeiro fetch, o cache deve ser usado."""
        from routes import api as api_module

        # Reseta o cache
        api_module._cidades_cache['ts'] = 0.0
        api_module._cidades_cache['dados'] = []

        dados_mock = [
            {'nome': 'Goiânia', 'microrregiao': {'mesorregiao': {'UF': {'sigla': 'GO'}}}},
            {'nome': 'Cuiabá',  'microrregiao': {'mesorregiao': {'UF': {'sigla': 'MT'}}}},
        ]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = dados_mock

        with patch('routes.api.requests.get', return_value=mock_resp) as mock_get:
            with app.test_client() as client:
                client.get('/proxy-cidades')
                client.get('/proxy-cidades')

            # requests.get deve ter sido chamado UMA única vez
            assert mock_get.call_count == 1, (
                f"requests.get foi chamado {mock_get.call_count}x — cache não está funcionando"
            )

    def test_cache_expira_apos_ttl(self, app):
        """Após TTL, a próxima chamada deve buscar novamente."""
        from routes import api as api_module

        # Força o cache como expirado
        api_module._cidades_cache['ts'] = time.time() - (25 * 3600)  # 25h atrás
        api_module._cidades_cache['dados'] = [{'nome': 'Antigo', 'uf': 'XX'}]

        dados_novos = [
            {'nome': 'Goiânia', 'microrregiao': {'mesorregiao': {'UF': {'sigla': 'GO'}}}},
        ]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = dados_novos

        with patch('routes.api.requests.get', return_value=mock_resp) as mock_get:
            with app.test_client() as client:
                client.get('/proxy-cidades')

            assert mock_get.call_count == 1, "Cache expirado deve refazer o request"

    def test_retorna_cidades_formatadas(self, app):
        """Resposta deve conter nome e uf."""
        from routes import api as api_module

        api_module._cidades_cache['ts'] = 0.0
        api_module._cidades_cache['dados'] = []

        dados_mock = [
            {'nome': 'Goiânia', 'microrregiao': {'mesorregiao': {'UF': {'sigla': 'GO'}}}},
        ]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = dados_mock

        with patch('routes.api.requests.get', return_value=mock_resp):
            with app.test_client() as client:
                resp = client.get('/proxy-cidades')
                assert resp.status_code == 200
                data = resp.get_json()
                assert isinstance(data, list)
                assert data[0]['nome'] == 'Goiânia'
                assert data[0]['uf'] == 'GO'


# ══════════════════════════════════════════════════════════════════════════════
# M6 — Cache-Control headers nas respostas JSON da API
# ══════════════════════════════════════════════════════════════════════════════

class TestCacheControlHeaders:
    """M6 — Endpoints de métricas devem incluir Cache-Control nas respostas."""

    def _login(self, client):
        client.post('/login', data={'username': 'testuser', 'password': '123'})

    def test_dashboard_summary_tem_cache_control(self, app):
        with app.test_client() as client:
            self._login(client)
            resp = client.get('/api/dashboard-summary')
            assert resp.status_code == 200
            cc = resp.headers.get('Cache-Control', '')
            assert 'max-age' in cc, f"Cache-Control ausente ou sem max-age: '{cc}'"

    def test_graficos_sexo_tem_cache_control(self, app):
        with app.test_client() as client:
            self._login(client)
            resp = client.get('/api/graficos/sexo')
            assert resp.status_code == 200
            cc = resp.headers.get('Cache-Control', '')
            assert 'max-age' in cc

    def test_graficos_gmd_tem_cache_control(self, app):
        with app.test_client() as client:
            self._login(client)
            resp = client.get('/api/graficos/gmd')
            assert resp.status_code == 200
            cc = resp.headers.get('Cache-Control', '')
            assert 'max-age' in cc
