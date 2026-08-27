-- 0002.seed-cost-centers
-- Dados de referencia: centros de custo fixos que a UI de custos operacionais
-- assume existir. INSERT IGNORE = convergente (no-op se ja povoado).
-- Espelha o antigo seeder de init_db.criar_schema().

INSERT IGNORE INTO `cost_centers` (`nome`, `categoria`) VALUES
  ('Arrendamento', 'Fixo'),
  ('Salário',      'Fixo'),
  ('Manutenção',   'Fixo'),
  ('Outros',       'Fixo'),
  ('Nutrição',     'Variavel'),
  ('Sanitário',    'Variavel'),
  ('Frete',        'Variavel'),
  ('Outros',       'Variavel');
