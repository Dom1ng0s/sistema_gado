"""Refresh das materialized views de cálculo pesado (#115).

`v_gmd_analitico`, `v_fluxo_caixa` e `vw_resultado_lote` são materialized views
(migration 0003). O app lê delas em vez de recalcular window functions e
agregações por request; este job as atualiza periodicamente.

Agendado no app.py a cada 5 min, no processo master do Gunicorn (o mesmo guard
`SCHEDULER_ENABLED` dos alertas). `REFRESH ... CONCURRENTLY` não bloqueia leitura
e exige o índice único que a 0003 cria — e **não pode** rodar em transação, daí
a conexão com autocommit.
"""
import logging

import db_config

logger = logging.getLogger(__name__)

MATVIEWS = ("v_gmd_analitico", "v_fluxo_caixa", "vw_resultado_lote")


def refresh_matviews(app=None):
    try:
        conn = db_config.connect(autocommit=True)
    except Exception as e:  # noqa: BLE001
        logger.error("refresh_matviews: sem conexão (%s)", e)
        return
    try:
        with conn.cursor() as cur:
            for mv in MATVIEWS:
                cur.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv}")
        logger.info("Materialized views atualizadas: %s", ", ".join(MATVIEWS))
    except Exception as e:  # noqa: BLE001
        logger.error("refresh_matviews falhou: %s", e, exc_info=True)
    finally:
        conn.close()
