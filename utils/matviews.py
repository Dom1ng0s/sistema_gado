"""Refresh das materialized views de cálculo pesado (#115, #117).

`v_gmd_analitico`, `v_fluxo_caixa` e `vw_resultado_lote` são materialized views
(migration 0003). O app lê delas em vez de recalcular window functions e
agregações por request; este job as atualiza periodicamente.

Agendado no app.py a cada 5 min, no processo master do Gunicorn (o mesmo guard
`SCHEDULER_ENABLED` dos alertas). `REFRESH ... CONCURRENTLY` não bloqueia leitura
e exige o índice único que a 0003 cria — e **não pode** rodar em transação, daí
a conexão com autocommit.

O refresh incondicional era a parede de escala (#117): custo proporcional à base
inteira, a cada 5 minutos, para sempre, mesmo sem ninguém ter escrito nada.
Agora cada matview só é refeita quando as tabelas que a alimentam receberam
escrita desde a última vez. Quem conta é o próprio Postgres, em
`pg_stat_user_tables` — sem trigger, sem nada no caminho da escrita, e sem uma
coluna `atualizado_em` para manter em todo INSERT do sistema.
"""
import logging

import db_config

logger = logging.getLogger(__name__)

MATVIEWS = ("v_gmd_analitico", "v_fluxo_caixa", "vw_resultado_lote")

#: Tabelas que alimentam cada matview — tiradas da definição das views em
#: migrations/0001. Tabela de fora desta lista não dispara refresh, então
#: mexer na definição de uma view pede mexer aqui junto.
FONTES = {
    "v_gmd_analitico":   ("pesagens", "animais"),
    "v_fluxo_caixa":     ("animais", "medicacoes", "custos_operacionais"),
    "vw_resultado_lote": ("lotes", "animais", "medicacoes"),
}


def precisa_refresh(gravado, atual):
    """A matview está desatualizada?

    `gravado` é a contagem de escritas de quando ela foi atualizada pela última
    vez; `atual`, a de agora. Nunca vista antes (None) sempre refaz.

    `atual < gravado` significa que os contadores do Postgres zeraram
    (`pg_stat_reset`, recuperação de crash): nesse caso não dá para saber o que
    passou, e refazer é a resposta segura.
    """
    if gravado is None:
        return True
    return atual != gravado


def _escritas(cur, tabelas):
    """Escritas acumuladas nas tabelas de origem, segundo o próprio Postgres."""
    cur.execute(
        "SELECT COALESCE(SUM(n_tup_ins + n_tup_upd + n_tup_del), 0) "
        "FROM pg_stat_user_tables WHERE relname = ANY(%s)",
        (list(tabelas),)
    )
    return int(cur.fetchone()[0])


def _estado(cur):
    cur.execute("SELECT nome, escritas FROM matview_estado")
    return {nome: escritas for nome, escritas in cur.fetchall()}


def refresh_matviews(app=None):
    try:
        conn = db_config.connect(autocommit=True)
    except Exception as e:  # noqa: BLE001
        logger.error("refresh_matviews: sem conexão (%s)", e)
        return
    try:
        with conn.cursor() as cur:
            try:
                gravados = _estado(cur)
            except Exception as e:  # noqa: BLE001
                # Banco ainda sem a migration 0009: segue refazendo tudo, que é
                # o comportamento antigo, em vez de parar de atualizar.
                logger.warning("matview_estado indisponível (%s) — refresh incondicional", e)
                gravados = None

            refeitas, puladas = [], []
            for mv in MATVIEWS:
                atual = _escritas(cur, FONTES[mv]) if gravados is not None else None
                if gravados is not None and not precisa_refresh(gravados.get(mv), atual):
                    puladas.append(mv)
                    continue

                cur.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv}")
                refeitas.append(mv)

                if gravados is not None:
                    # Relê depois do refresh: o próprio REFRESH não escreve nas
                    # tabelas de origem, mas alguém pode ter escrito enquanto
                    # ele rodava, e gravar o valor de antes perderia essa
                    # escrita até a próxima.
                    cur.execute(
                        "INSERT INTO matview_estado (nome, ultimo_refresh, escritas) "
                        "VALUES (%s, now(), %s) "
                        "ON CONFLICT (nome) DO UPDATE SET ultimo_refresh = now(), "
                        "escritas = EXCLUDED.escritas",
                        (mv, _escritas(cur, FONTES[mv]))
                    )

        if refeitas:
            logger.info("Materialized views atualizadas: %s%s",
                        ", ".join(refeitas),
                        f" (sem escrita desde o último refresh: {', '.join(puladas)})"
                        if puladas else "")
        else:
            logger.debug("Nenhuma escrita desde o último refresh — nada a refazer.")
    except Exception as e:  # noqa: BLE001
        logger.error("refresh_matviews falhou: %s", e, exc_info=True)
    finally:
        conn.close()
