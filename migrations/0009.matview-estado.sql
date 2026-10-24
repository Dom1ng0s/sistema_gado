-- 0009.matview-estado  (SGG+ — issue #117)
-- `refresh_matviews` roda REFRESH CONCURRENTLY das três matviews a cada 5
-- minutos, de todos os tenants, para sempre — inclusive na madrugada, inclusive
-- quando ninguém escreveu nada desde o último refresh. O custo cresce com a
-- base inteira e não com o uso, que é a definição de parede de escala.
--
-- Esta tabela guarda, por matview, quantas escritas o banco já tinha contado
-- nas tabelas que a alimentam quando ela foi atualizada pela última vez. Se o
-- número não mudou, não há o que refazer.
--
-- A contagem vem de `pg_stat_user_tables` (n_tup_ins + n_tup_upd + n_tup_del):
-- é o próprio Postgres contando, sem trigger e sem nada no caminho da escrita.
CREATE TABLE IF NOT EXISTS matview_estado (
    nome           text PRIMARY KEY,
    ultimo_refresh timestamptz,
    escritas       bigint NOT NULL DEFAULT 0
);
