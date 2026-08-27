-- 0002.seed-cost-centers
-- Dados de referência: centros de custo fixos que a UI de custos operacionais
-- assume existir. ON CONFLICT DO NOTHING = convergente (no-op se já povoado).

INSERT INTO cost_centers (nome, categoria) VALUES
  ('Arrendamento', 'Fixo'),
  ('Salário',      'Fixo'),
  ('Manutenção',   'Fixo'),
  ('Outros',       'Fixo'),
  ('Nutrição',     'Variavel'),
  ('Sanitário',    'Variavel'),
  ('Frete',        'Variavel'),
  ('Outros',       'Variavel')
ON CONFLICT (nome, categoria) DO NOTHING;
