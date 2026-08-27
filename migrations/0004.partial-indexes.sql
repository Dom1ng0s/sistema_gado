-- 0004.partial-indexes  (#115)
-- Índices parciais para o soft-delete: quase toda query do app filtra
-- `deleted_at IS NULL`. Um índice parcial é menor (só as linhas vivas) e o
-- planner do Postgres o usa direto quando a query tem o mesmo predicado.
-- Complementa os índices compostos que já carregam deleted_at como coluna.

CREATE INDEX IF NOT EXISTS ix_animais_vivos
    ON animais (user_id) WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_pesagens_vivas
    ON pesagens (animal_id, data_pesagem) WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_medicacoes_vivas
    ON medicacoes (animal_id, data_aplicacao) WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_custos_vivos
    ON custos_operacionais (user_id, data_custo) WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_financial_schedule_vivos
    ON financial_schedule (user_id, vencimento) WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_lotes_vivos
    ON lotes (user_id) WHERE deleted_at IS NULL;
