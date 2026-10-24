-- 0008.webhook  (SGG+ PR 4b)
-- O webhook do provider de pagamento recebe eventos que nem sempre dá para
-- ligar a uma conta: link de pagamento genérico, cobrança feita fora do fluxo,
-- cliente que pagou com outro email. Esses eventos são exatamente os que
-- precisam ser guardados — são eles que a conciliação vai procurar — então
-- `user_id` deixa de ser obrigatório.
--
-- O resto da tabela já está certo desde a 0007: o UNIQUE (provider,
-- provider_event_id) é o que torna o endpoint idempotente, porque o provider
-- reenvia o mesmo evento até receber 200.
ALTER TABLE pagamentos ALTER COLUMN user_id DROP NOT NULL;

-- Que evento era. Sem isso, `status` sozinho não distingue um pagamento
-- confirmado de um estorno confirmado.
ALTER TABLE pagamentos ADD COLUMN IF NOT EXISTS evento varchar(60);

-- A fila de conciliação: o que chegou e não achou dono.
CREATE INDEX IF NOT EXISTS ix_pagamentos_orfaos
    ON pagamentos (created_at DESC) WHERE user_id IS NULL;
