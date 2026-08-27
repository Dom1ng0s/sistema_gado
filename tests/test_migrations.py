"""Guardas da camada de migrations (#114) e da política só-aditiva de schema (#78)."""
import pathlib
import re

import pytest

from db_migrate import MIGRATIONS_DIR
from yoyo import read_migrations

_FILES = sorted(pathlib.Path(MIGRATIONS_DIR).glob("*.sql"))


def test_ha_migrations_e_estao_ordenadas():
    ids = [m.id for m in read_migrations(MIGRATIONS_DIR)]
    assert ids, "nenhuma migration encontrada"
    assert ids == sorted(ids), f"migrations fora de ordem: {ids}"
    assert ids[0] == "0001.baseline-schema"


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.stem)
def test_migration_nao_e_destrutiva(path):
    """#78 — migração só-aditiva: nada de DROP TABLE / DROP COLUMN / DROP DATABASE.

    (DROP VIEW / CREATE OR REPLACE VIEW é permitido — view é derivada, não dado.)
    """
    sql = path.read_text(encoding="utf-8")
    # tira comentários de linha antes de procurar
    sql_sem_comentario = re.sub(r"--.*", "", sql)
    proibidos = re.findall(
        r"\bDROP\s+(TABLE|COLUMN|DATABASE|SCHEMA)\b",
        sql_sem_comentario,
        re.IGNORECASE,
    )
    assert not proibidos, f"{path.name}: DDL destrutiva {proibidos}"


def test_baseline_cria_o_schema_esperado(db_setup):
    """db_setup roda as migrations no banco de teste — confere que as tabelas
    e views centrais existem."""
    import conftest
    import mysql.connector

    conn = mysql.connector.connect(**conftest.TEST_DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        "SELECT table_name, table_type FROM information_schema.tables "
        "WHERE table_schema = %s",
        (conftest.TEST_DB_NAME,),
    )
    objetos = {nome for nome, _ in cur.fetchall()}
    conn.close()

    for tabela in ("animais", "pesagens", "lotes", "reproducao", "cost_centers",
                   "estoque_movimentacoes", "protocolos_sanitarios"):
        assert tabela in objetos, f"tabela ausente: {tabela}"
    for view in ("v_gmd_analitico", "v_fluxo_caixa", "vw_resultado_lote",
                 "vw_saldo_estoque"):
        assert view in objetos, f"view ausente: {view}"
    assert "_yoyo_migration" in objetos, "yoyo não registrou as migrations"
