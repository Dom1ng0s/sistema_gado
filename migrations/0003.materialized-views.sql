-- 0003.materialized-views  (#115)
-- Converte as 3 views de cálculo pesado em MATERIALIZED VIEW. O corpo do SELECT
-- fica numa view normal `*_live` (fonte única de verdade, sem duplicar SQL) e a
-- matview só faz `SELECT * FROM *_live`. Assim:
--   - produção: app lê a matview (barata: index scan), refresh a cada 5 min
--     pelo job do APScheduler (app.py). REFRESH ... CONCURRENTLY exige o índice
--     único abaixo e não bloqueia leitura.
--   - testes: conftest.py troca a matview por uma view normal sobre `*_live`,
--     recuperando consistência read-after-write sem recopiar o SELECT.
--
-- Trade-off: o GMD/financeiro do painel fica até ~5 min defasado de uma pesagem
-- ou lançamento novo. Aceitável para gestão de fazenda (dados entram em lote).

ALTER VIEW v_gmd_analitico   RENAME TO v_gmd_analitico_live;
ALTER VIEW v_fluxo_caixa     RENAME TO v_fluxo_caixa_live;
ALTER VIEW vw_resultado_lote RENAME TO vw_resultado_lote_live;

CREATE MATERIALIZED VIEW v_gmd_analitico   AS SELECT * FROM v_gmd_analitico_live;
CREATE MATERIALIZED VIEW v_fluxo_caixa     AS SELECT * FROM v_fluxo_caixa_live;
CREATE MATERIALIZED VIEW vw_resultado_lote AS SELECT * FROM vw_resultado_lote_live;

-- Índice UNIQUE: obrigatório para REFRESH MATERIALIZED VIEW ... CONCURRENTLY.
CREATE UNIQUE INDEX ux_v_gmd_analitico_animal   ON v_gmd_analitico (animal_id);
CREATE UNIQUE INDEX ux_v_fluxo_caixa_user_ano   ON v_fluxo_caixa (user_id, ano);
CREATE UNIQUE INDEX ux_vw_resultado_lote_lote   ON vw_resultado_lote (lote_id);

-- Índices de leitura: todo acesso do app filtra por user_id.
CREATE INDEX ix_v_gmd_analitico_user   ON v_gmd_analitico (user_id);
CREATE INDEX ix_vw_resultado_lote_user ON vw_resultado_lote (user_id);
