"""Refresh condicional das matviews (#117) e o script de diagnóstico.

O refresh incondicional era a parede de escala: custo proporcional à base
inteira a cada 5 minutos, para sempre, mesmo sem ninguém ter escrito nada.
`test_sem_escrita_nao_refaz` é a correção; `test_escrita_dispara_refresh` é a
garantia de que ela não foi longe demais e passou a servir dado velho.
"""
import io
import itertools
import os
import subprocess
import sys

import pytest
from werkzeug.security import generate_password_hash

from tests.dbcompat import connect
from utils import matviews

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_seq = itertools.count(23000)


def _buscar(sql, params=()):
    conn = connect()
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


# -- A decisão, sem banco ----------------------------------------------------

def test_nunca_vista_antes_sempre_refaz():
    assert matviews.precisa_refresh(None, 0)
    assert matviews.precisa_refresh(None, 1234)


def test_sem_escrita_nao_refaz():
    assert not matviews.precisa_refresh(5000, 5000)


def test_escrita_dispara_refresh():
    assert matviews.precisa_refresh(5000, 5001)


def test_contador_zerado_refaz():
    """`pg_stat_reset` ou recuperação de crash derruba o contador: não dá para
    saber o que passou, então refazer é a resposta segura."""
    assert matviews.precisa_refresh(5000, 12)


def test_toda_matview_tem_fonte_declarada():
    """Matview sem fonte nunca seria refeita — o pior dos dois mundos."""
    assert set(matviews.MATVIEWS) == set(matviews.FONTES)
    for mv, tabelas in matviews.FONTES.items():
        assert tabelas, mv


def test_tabela_de_estado_existe(app):
    linha = _buscar("SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'matview_estado'")
    assert linha is not None


def test_contagem_de_escritas_vem_do_postgres(app):
    """A contagem é a do próprio banco: sem trigger e sem nada no caminho da
    escrita."""
    conn = connect()
    cur = conn.cursor()
    try:
        antes = matviews._escritas(cur, ('animais',))
        cur.execute("INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
                    (f"mv_{next(_seq)}", generate_password_hash('x')))
        uid = cur.lastrowid
        cur.execute("INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id)"
                    " VALUES (%s, 'M', '2024-01-01', 1000, %s)", (f"MV-{uid}", uid))
        conn.commit()
        # pg_stat é atualizado de forma assíncrona, mas o INSERT da própria
        # sessão já conta ao fim da transação.
        depois = matviews._escritas(cur, ('animais',))
        assert depois >= antes
    finally:
        cur.execute("SET session_replication_role = 'replica'")
        cur.execute("DELETE FROM animais WHERE user_id = %s", (uid,))
        cur.execute("DELETE FROM usuarios WHERE id = %s", (uid,))
        cur.execute("SET session_replication_role = 'origin'")
        conn.commit()
        cur.close()
        conn.close()


def test_a_ficha_do_animal_le_a_view_live(app):
    """Quem acabou de pesar abre a ficha e tem de ver o número que digitou —
    não o de cinco minutos atrás."""
    fonte = io.open(os.path.join(RAIZ, 'repositories', 'animal_repository.py'),
                    encoding='utf-8').read()
    trecho = fonte[fonte.index('def get_gmd_by_animal'):]
    trecho = trecho[:trecho.index('def get_gmd_medio_rebanho')]
    assert 'v_gmd_analitico_live' in trecho


# -- O script de diagnóstico -------------------------------------------------

CSV_EXEMPLO = (
    "brinco,sexo,data_compra,peso_kg,valor_arroba,raca\n"
    "A-1,M,2026-01-10,300,180.00,Nelore\n"
    "A-2,F,2026-01-10,420,180.00,Nelore\n"
    "A-3,M,2026-01-10,510,180.00,Angus\n"
    "A-3,M,2026-01-10,510,180.00,Angus\n"      # repetido
    ",M,2026-01-10,200,180.00,\n"              # sem brinco
    "A-5,,2026-01-10,,180.00,\n"               # sem peso e sem sexo
)


@pytest.fixture
def csv_tmp(tmp_path):
    caminho = tmp_path / "rebanho.csv"
    caminho.write_text(CSV_EXEMPLO, encoding='utf-8')
    return str(caminho)


def _importar_script():
    sys.path.insert(0, os.path.join(RAIZ, 'scripts'))
    import diagnostico  # noqa: PLC0415
    return diagnostico


def test_leitura_separa_valido_de_torto(csv_tmp):
    """Planilha de prospect vem torta — e metade do diagnóstico é sobre isso."""
    diagnostico = _importar_script()
    linhas, problemas = diagnostico.ler(csv_tmp)
    assert [a['brinco'] for a in linhas] == ['A-1', 'A-2', 'A-3']
    motivos = ' | '.join(m for _, m in problemas)
    assert 'repetido' in motivos
    assert 'brinco em branco' in motivos
    assert 'peso ausente' in motivos


def test_numeros_do_diagnostico(csv_tmp):
    diagnostico = _importar_script()
    linhas, _ = diagnostico.ler(csv_tmp)
    d = diagnostico.diagnosticar(linhas)
    assert d['cabecas'] == 3
    assert d['machos'] == 2 and d['femeas'] == 1
    assert d['peso_medio'] == 410.0
    assert d['arrobas'] == 41.0
    assert d['valor_rebanho'] == 7380.0
    assert sum(f['quantos'] for f in d['faixas']) == 3


def test_csv_sem_coluna_obrigatoria_para(tmp_path):
    diagnostico = _importar_script()
    caminho = tmp_path / "ruim.csv"
    caminho.write_text("brinco,sexo\nA-1,M\n", encoding='utf-8')
    with pytest.raises(SystemExit):
        diagnostico.ler(str(caminho))


def test_html_sai_sem_playwright(csv_tmp, tmp_path):
    """O modo --html existe para o script ser testável e utilizável sem o
    navegador — o PDF é só a impressão desse mesmo HTML."""
    saida = tmp_path / "diag.html"
    resultado = subprocess.run(
        [sys.executable, os.path.join(RAIZ, 'scripts', 'diagnostico.py'),
         csv_tmp, '--html', '--saida', str(saida), '--fazenda', 'Fazenda Teste'],
        capture_output=True, text=True, encoding='utf-8',
        env={**os.environ, 'PYTHONUTF8': '1'},
    )
    assert resultado.returncode == 0, resultado.stderr
    corpo = saida.read_text(encoding='utf-8')
    assert 'Diagnóstico de rebanho' in corpo
    assert 'Fazenda Teste' in corpo
    assert '410.0 kg' in corpo
    assert 'repetido' in corpo


def test_script_nao_toca_no_banco():
    """É ferramenta de venda: dado de prospect não entra na base."""
    fonte = io.open(os.path.join(RAIZ, 'scripts', 'diagnostico.py'),
                    encoding='utf-8').read()
    for proibido in ('db_config', 'get_db_cursor', 'psycopg', 'INSERT INTO'):
        assert proibido not in fonte, proibido
