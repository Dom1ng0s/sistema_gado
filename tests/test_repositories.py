"""
Testes dos repositórios: correctness das queries e isolamento por user_id.
Cada teste cria seus próprios usuários isolados e limpa ao terminar.
"""
import pytest
import itertools
from datetime import date, timedelta
from werkzeug.security import generate_password_hash
import db_config as dbc
from repositories import animal_repository, financeiro_repository, configuracao_repository

_seq = itertools.count(1000)


def _n():
    return next(_seq)


# ── Helpers de banco (chamados após o fixture `app` já ter patchado db_config) ──

def _make_user():
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
        (f"ru_{_n()}", generate_password_hash("x")),
    )
    uid = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return uid


def _make_animal(user_id, brinco=None, preco=1000.0, sexo="M"):
    brinco = brinco or f"BR{_n()}"
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id)"
        " VALUES (%s, %s, '2024-01-01', %s, %s)",
        (brinco, sexo, preco, user_id),
    )
    aid = cur.lastrowid
    cur.execute(
        "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, '2024-01-01', 300.0)",
        (aid,),
    )
    conn.commit()
    cur.close()
    conn.close()
    return aid


def _make_pesagem(animal_id, peso=350.0):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, '2024-06-01', %s)",
        (animal_id, peso),
    )
    pid = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return pid


def _fetch_one(sql, params):
    """Executa um SELECT pontual no banco de teste. Uso restrito a infraestrutura de testes."""
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def _count(sql, params):
    row = _fetch_one(sql, params)
    return row[0] if row else 0


def _purge(user_id):
    conn = dbc.get_db_connection()
    cur = conn.cursor()
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    for sql in [
        "DELETE oa FROM ocupacao_animais oa JOIN ocupacoes o ON oa.ocupacao_id = o.id JOIN modulos m ON o.modulo_id = m.id WHERE m.user_id = %s",
        "DELETE o FROM ocupacoes o JOIN modulos m ON o.modulo_id = m.id WHERE m.user_id = %s",
        "DELETE FROM modulos WHERE user_id = %s",
        "DELETE FROM pastos WHERE user_id = %s",
        "DELETE p FROM pesagens p JOIN animais a ON p.animal_id = a.id WHERE a.user_id = %s",
        "DELETE m FROM medicacoes m JOIN animais a ON m.animal_id = a.id WHERE a.user_id = %s",
        "DELETE FROM reproducao WHERE user_id = %s",
        "DELETE FROM animais WHERE user_id = %s",
        "DELETE FROM estoque_movimentacoes WHERE user_id = %s",
        "DELETE FROM estoque_produtos WHERE user_id = %s",
        "DELETE FROM lotes WHERE user_id = %s",
        "DELETE FROM custos_operacionais WHERE user_id = %s",
        "DELETE FROM financial_schedule WHERE user_id = %s",
        "DELETE FROM configuracoes WHERE user_id = %s",
        "DELETE FROM usuarios WHERE id = %s",
    ]:
        cur.execute(sql, (user_id,))
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()
    cur.close()
    conn.close()


@pytest.fixture
def dois(app):
    """Par de usuários isolados; limpeza automática após cada teste."""
    uid_a, uid_b = _make_user(), _make_user()
    yield uid_a, uid_b
    _purge(uid_a)
    _purge(uid_b)


@pytest.fixture
def um(app):
    """Um usuário isolado; limpeza automática após cada teste."""
    uid = _make_user()
    yield uid
    _purge(uid)


# ════════════════════════════════════════════════════════════════════════════
# ISOLAMENTO — animal_repository
# ════════════════════════════════════════════════════════════════════════════

def test_get_animal_by_id_usuario_errado_retorna_none(dois):
    uid_a, uid_b = dois
    aid = _make_animal(uid_a)
    assert animal_repository.get_animal_by_id(aid, uid_b) is None


def test_get_animal_by_id_usuario_correto_retorna_dados(dois):
    uid_a, uid_b = dois
    aid = _make_animal(uid_a)
    assert animal_repository.get_animal_by_id(aid, uid_a) is not None


def test_soft_delete_usuario_errado_nao_altera_dado(dois):
    uid_a, uid_b = dois
    aid = _make_animal(uid_a)
    assert animal_repository.soft_delete_animal(aid, uid_b) is False
    row = _fetch_one("SELECT deleted_at FROM animais WHERE id = %s", (aid,))
    assert row[0] is None


def test_registrar_venda_usuario_errado_nao_modifica_animal(dois):
    uid_a, uid_b = dois
    aid = _make_animal(uid_a)
    assert animal_repository.registrar_venda(aid, uid_b, "2024-06-01", 5000.0, 500.0) is False
    row = _fetch_one("SELECT data_venda FROM animais WHERE id = %s", (aid,))
    assert row[0] is None


def test_registrar_pesagem_usuario_errado_nao_cria_registro(dois):
    uid_a, uid_b = dois
    aid = _make_animal(uid_a)
    n_antes = _count("SELECT COUNT(*) FROM pesagens WHERE animal_id = %s", (aid,))
    assert animal_repository.registrar_pesagem(aid, uid_b, "2024-06-01", 400.0) is False
    assert _count("SELECT COUNT(*) FROM pesagens WHERE animal_id = %s", (aid,)) == n_antes


def test_registrar_medicacao_usuario_errado_nao_cria_registro(dois):
    uid_a, uid_b = dois
    aid = _make_animal(uid_a)
    assert animal_repository.registrar_medicacao(aid, uid_b, "2024-06-01", "Iver", 50.0, "") is False
    assert _count("SELECT COUNT(*) FROM medicacoes WHERE animal_id = %s", (aid,)) == 0


def test_soft_delete_pesagem_usuario_errado_retorna_none(dois):
    uid_a, uid_b = dois
    aid = _make_animal(uid_a)
    pid = _make_pesagem(aid)
    assert animal_repository.soft_delete_pesagem(pid, uid_b) is None
    row = _fetch_one("SELECT deleted_at FROM pesagens WHERE id = %s", (pid,))
    assert row[0] is None


def test_get_animal_id_by_pesagem_usuario_errado_retorna_none(dois):
    uid_a, uid_b = dois
    aid = _make_animal(uid_a)
    pid = _make_pesagem(aid)
    assert animal_repository.get_animal_id_by_pesagem(pid, uid_b) is None
    assert animal_repository.get_animal_id_by_pesagem(pid, uid_a) == aid


# ════════════════════════════════════════════════════════════════════════════
# CORRECTNESS — animal_repository
# ════════════════════════════════════════════════════════════════════════════

def test_registrar_pesagens_lote_ignora_animal_soft_deletado(um):
    """Issue #34 — a validação de propriedade do batch deve descartar animais
    na lixeira, igual à versão de animal único."""
    aid = _make_animal(um)
    animal_repository.soft_delete_animal(aid, um)
    n_antes = _count("SELECT COUNT(*) FROM pesagens WHERE animal_id = %s", (aid,))
    inseridos, invalidos = animal_repository.registrar_pesagens_lote(
        [(aid, 400.0)], um, "2024-06-01"
    )
    assert inseridos == 0
    assert invalidos == [aid]
    assert _count("SELECT COUNT(*) FROM pesagens WHERE animal_id = %s", (aid,)) == n_antes


def test_check_brinco_exists_false_depois_true(um):
    brinco = f"BX{_n()}"
    assert animal_repository.check_brinco_exists(brinco, um) is False
    _make_animal(um, brinco)
    assert animal_repository.check_brinco_exists(brinco, um) is True


def test_cadastrar_animal_cria_pesagem_inicial(um):
    aid = animal_repository.cadastrar_animal(f"CAD{_n()}", "F", "2024-01-01", 1000.0, 280.0, um)
    pesagens = animal_repository.get_pesagens_by_animal(aid)
    assert len(pesagens) == 1
    assert float(pesagens[0][3]) == pytest.approx(280.0)  # índice 3 = peso


def test_normalizar_raca_canonicaliza_variacoes():
    """Trim, colapso de espaços e Title Case reduzem variações à mesma forma."""
    assert animal_repository._normalizar_raca("nelore ") == "Nelore"
    assert animal_repository._normalizar_raca("NELORE") == "Nelore"
    assert animal_repository._normalizar_raca("  red  angus ") == "Red Angus"
    assert animal_repository._normalizar_raca("") is None
    assert animal_repository._normalizar_raca(None) is None


def test_get_racas_distintas_agrupa_variacoes(um):
    """Duas grafias da mesma raça na escrita → um único valor no dropdown."""
    animal_repository.cadastrar_animal(f"RC{_n()}", "F", "2024-01-01", 1000.0, 280.0, um, raca="nelore ")
    animal_repository.cadastrar_animal(f"RC{_n()}", "M", "2024-01-01", 1000.0, 280.0, um, raca="NELORE")
    racas = animal_repository.get_racas_distintas(um)
    assert racas.count("Nelore") == 1
    assert "nelore " not in racas and "NELORE" not in racas


def test_cadastrar_lote_associa_pesagem_ao_animal_correto(um):
    """cadastrar_lote insere animais e pesagens via executemany, mapeando o
    animal_id de volta por brinco — cada pesagem tem que ficar com o animal certo,
    não embaralhada entre os animais do mesmo lote."""
    animais_data = [
        (f"LOTE{_n()}A", "M", 250.0, 900.0),
        (f"LOTE{_n()}B", "F", 300.0, 1100.0),
        (f"LOTE{_n()}C", "M", 275.0, 950.0),
    ]
    lote_id = animal_repository.cadastrar_lote(um, f"L{_n()}", "Lote teste", "2024-01-01", animais_data)
    assert lote_id is not None

    for brinco, sexo, peso, custo in animais_data:
        row = _fetch_one("SELECT id, sexo, preco_compra FROM animais WHERE brinco = %s AND user_id = %s", (brinco, um))
        assert row is not None
        aid, sexo_db, preco_db = row
        assert sexo_db == sexo
        assert float(preco_db) == pytest.approx(custo)
        pesagens = animal_repository.get_pesagens_by_animal(aid)
        assert len(pesagens) == 1
        assert float(pesagens[0][3]) == pytest.approx(peso)  # índice 3 = peso


def test_get_gmd_medio_rebanho_filtra_por_sexo(um):
    """sexo='M'/'F' restringe o cálculo ao grupo — segregação de matrizes do GMD geral."""
    macho = _make_animal(um, sexo="M")
    femea = _make_animal(um, sexo="F")
    _make_pesagem(macho, peso=400.0)  # +100kg
    _make_pesagem(femea, peso=310.0)  # +10kg

    gmd_m = animal_repository.get_gmd_medio_rebanho(um, sexo="M")
    gmd_f = animal_repository.get_gmd_medio_rebanho(um, sexo="F")
    gmd_todos = animal_repository.get_gmd_medio_rebanho(um)

    assert gmd_f < gmd_todos < gmd_m


def test_get_animais_abaixo_gmd_medio_identifica_outlier(um):
    """Animal com GMD muito abaixo da média - 2σ do rebanho deve aparecer como
    outlier; animais dentro da faixa normal não devem aparecer."""
    normais = [_make_animal(um) for _ in range(5)]
    for aid, peso in zip(normais, [452.0, 450.0, 455.0, 448.0, 453.0]):
        _make_pesagem(aid, peso=peso)  # GMD ~1.0 kg/dia

    outlier = _make_animal(um)
    _make_pesagem(outlier, peso=305.0)  # GMD ~0.03 kg/dia — crescimento estagnado

    resultado = animal_repository.get_animais_abaixo_gmd_medio(um)
    ids_outliers = {row[0] for row in resultado}

    assert outlier in ids_outliers
    assert not (set(normais) & ids_outliers)


def test_count_animais_status_todos_igual_ativos_mais_vendidos(um):
    aid_v = _make_animal(um)
    _make_animal(um)  # ativo
    animal_repository.registrar_venda(aid_v, um, "2024-06-01", 5000.0, 500.0)

    total = animal_repository.count_animais(um)
    ativos = animal_repository.count_animais(um, status="ativos")
    vendidos = animal_repository.count_animais(um, status="vendidos")
    assert total == ativos + vendidos
    assert ativos >= 1
    assert vendidos >= 1


def test_soft_delete_move_para_lixeira_e_remove_do_painel(um):
    aid = _make_animal(um)
    painel_antes = animal_repository.count_animais(um)
    lixeira_antes = animal_repository.count_animais_lixeira(um)

    animal_repository.soft_delete_animal(aid, um)

    assert animal_repository.count_animais(um) == painel_antes - 1
    assert animal_repository.count_animais_lixeira(um) == lixeira_antes + 1


def test_restore_devolve_animal_ao_painel(um):
    aid = _make_animal(um)
    animal_repository.soft_delete_animal(aid, um)
    painel_pos_delete = animal_repository.count_animais(um)

    animal_repository.restore_animal(aid, um)

    assert animal_repository.count_animais(um) == painel_pos_delete + 1
    assert animal_repository.count_animais_lixeira(um) == 0


def test_get_animais_ativos_exclui_vendidos_e_deletados(um):
    aid_ativo = _make_animal(um)
    aid_vendido = _make_animal(um)
    aid_deletado = _make_animal(um)
    animal_repository.registrar_venda(aid_vendido, um, "2024-06-01", 5000.0, 500.0)
    animal_repository.soft_delete_animal(aid_deletado, um)

    ids_ativos = [row[0] for row in animal_repository.get_animais_ativos(um)]
    assert aid_ativo in ids_ativos
    assert aid_vendido not in ids_ativos
    assert aid_deletado not in ids_ativos


def test_registrar_venda_atualiza_data_venda_e_cria_pesagem(um):
    aid = _make_animal(um)
    n_pes_antes = _count("SELECT COUNT(*) FROM pesagens WHERE animal_id = %s", (aid,))

    animal_repository.registrar_venda(aid, um, "2024-06-01", 5000.0, 500.0)

    row = _fetch_one("SELECT data_venda FROM animais WHERE id = %s", (aid,))
    assert row[0] is not None
    assert _count("SELECT COUNT(*) FROM pesagens WHERE animal_id = %s", (aid,)) == n_pes_antes + 1


def test_get_contagem_por_sexo_agrupa_corretamente(um):
    _make_animal(um, sexo="M")
    _make_animal(um, sexo="M")
    _make_animal(um, sexo="F")
    por_sexo = dict(animal_repository.get_contagem_por_sexo(um))
    assert por_sexo.get("M", 0) >= 2
    assert por_sexo.get("F", 0) >= 1


def test_soft_delete_pesagem_correto_retorna_animal_id_e_marca_deleted_at(um):
    aid = _make_animal(um)
    pid = _make_pesagem(aid)

    result = animal_repository.soft_delete_pesagem(pid, um)

    assert result == aid
    row = _fetch_one("SELECT deleted_at FROM pesagens WHERE id = %s", (pid,))
    assert row[0] is not None


def test_get_pesagens_by_animal_retorna_em_ordem_decrescente(um):
    aid = _make_animal(um)  # pesagem de 2024-01-01 criada pelo helper
    _make_pesagem(aid)      # pesagem de 2024-06-01

    pesagens = animal_repository.get_pesagens_by_animal(aid)
    datas = [row[2] for row in pesagens]  # índice 2 = data_pesagem
    assert datas == sorted(datas, reverse=True)


# ════════════════════════════════════════════════════════════════════════════
# ISOLAMENTO — financeiro_repository
# ════════════════════════════════════════════════════════════════════════════

def test_baixar_agendamento_usuario_errado_nao_altera_status(dois):
    uid_a, uid_b = dois
    financeiro_repository.insert_agendamento(uid_a, "Conta Luz", 200.0, "2024-12-31")
    ag_id = financeiro_repository.get_agendamentos(uid_a)[0][0]

    assert financeiro_repository.baixar_agendamento(ag_id, uid_b) is False

    row = _fetch_one("SELECT status FROM financial_schedule WHERE id = %s", (ag_id,))
    assert row[0] == "pendente"


# ════════════════════════════════════════════════════════════════════════════
# CORRECTNESS — financeiro_repository
# ════════════════════════════════════════════════════════════════════════════

def test_get_valor_rebanho_soma_apenas_animais_ativos(um):
    assert financeiro_repository.get_valor_rebanho(um) == pytest.approx(0.0)

    aid1 = _make_animal(um, preco=1000.0)
    aid2 = _make_animal(um, preco=2000.0)
    assert financeiro_repository.get_valor_rebanho(um) == pytest.approx(3000.0)

    # Animal vendido não entra na soma
    animal_repository.registrar_venda(aid2, um, "2024-06-01", 9000.0, 500.0)
    assert financeiro_repository.get_valor_rebanho(um) == pytest.approx(1000.0)

    # Animal deletado também não entra
    animal_repository.soft_delete_animal(aid1, um)
    assert financeiro_repository.get_valor_rebanho(um) == pytest.approx(0.0)


def test_insert_e_get_custos_por_ano(um):
    ano = date.today().year
    financeiro_repository.insert_custo_operacional(
        um, "Fixo", "Salário", 500.0, date.today().isoformat(), "Teste"
    )
    custos = financeiro_repository.get_custos_por_ano(um, ano)
    assert any(row[2] == "Salário" for row in custos)  # índice 2 = tipo_custo


def test_get_custos_por_ano_paginado_e_count(um):
    ano = date.today().year
    for i in range(3):
        financeiro_repository.insert_custo_operacional(
            um, "Fixo", f"Item{i}", 100.0, date.today().isoformat(), ""
        )

    total = financeiro_repository.count_custos_por_ano(um, ano)
    assert total >= 3

    pagina1 = financeiro_repository.get_custos_por_ano_paginado(um, ano, limit=2, offset=0)
    pagina2 = financeiro_repository.get_custos_por_ano_paginado(um, ano, limit=2, offset=2)
    assert len(pagina1) == 2
    assert len(pagina1) + len(pagina2) <= total
    # paginação não deve repetir linhas entre páginas
    assert not (set(map(tuple, pagina1)) & set(map(tuple, pagina2)))


def test_get_custos_por_tipo_trimestre_agrupa_e_filtra_data(um):
    dt_recente = (date.today() - timedelta(days=30)).isoformat()
    dt_antiga = (date.today() - timedelta(days=120)).isoformat()

    financeiro_repository.insert_custo_operacional(um, "Fixo", "Arrendamento", 300.0, dt_recente, "")
    financeiro_repository.insert_custo_operacional(um, "Fixo", "Arrendamento", 200.0, dt_recente, "")
    # Esta não deve entrar (fora dos 90 dias)
    financeiro_repository.insert_custo_operacional(um, "Fixo", "Arrendamento", 999.0, dt_antiga, "")

    dt_limite = date.today() - timedelta(days=90)
    resultado = dict(financeiro_repository.get_custos_por_tipo_trimestre(um, dt_limite))
    assert float(resultado.get("Arrendamento", 0)) == pytest.approx(500.0)


def test_insert_e_get_agendamentos(um):
    financeiro_repository.insert_agendamento(um, "Aluguel Máquina", 750.0, "2025-11-30")
    agendamentos = financeiro_repository.get_agendamentos(um)
    assert any(row[1] == "Aluguel Máquina" for row in agendamentos)  # índice 1 = descricao


def test_baixar_agendamento_correto_marca_pago_e_cria_custo(um):
    financeiro_repository.insert_agendamento(um, "Contrato Pasto", 1000.0, "2025-12-01")
    ag_id = financeiro_repository.get_agendamentos(um)[0][0]

    assert financeiro_repository.baixar_agendamento(ag_id, um) is True

    row = _fetch_one("SELECT status FROM financial_schedule WHERE id = %s", (ag_id,))
    assert row[0] == "pago"

    custos = financeiro_repository.get_custos_por_ano(um, date.today().year)
    assert any(row[2] == "Agendamento" for row in custos)


# ════════════════════════════════════════════════════════════════════════════
# CORRECTNESS — configuracao_repository
# ════════════════════════════════════════════════════════════════════════════

def test_get_configuracao_sem_registro_retorna_none(um):
    assert configuracao_repository.get_configuracao(um) is None


def test_upsert_cria_configuracao(um):
    configuracao_repository.upsert_configuracao(um, "Fazenda Teste", "Uberaba - MG", 150.0)
    res = configuracao_repository.get_configuracao(um)
    assert res is not None
    assert res[0] == "Fazenda Teste"
    assert res[1] == "Uberaba - MG"
    assert float(res[2]) == pytest.approx(150.0)


def test_upsert_atualiza_configuracao_existente(um):
    configuracao_repository.upsert_configuracao(um, "Fazenda Velha", "Cidade - SP", 100.0)
    configuracao_repository.upsert_configuracao(um, "Fazenda Nova", "Cidade - MG", 200.0)
    res = configuracao_repository.get_configuracao(um)
    assert res[0] == "Fazenda Nova"
    assert res[1] == "Cidade - MG"
    assert float(res[2]) == pytest.approx(200.0)
