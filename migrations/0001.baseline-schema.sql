-- 0001.baseline-schema
-- Estado consolidado do schema (tabelas + indices + views) tal como o antigo
-- init_db.criar_schema() convergia. Gerado com `mysqldump --no-data` e editado
-- para ser CONVERGENTE (IF NOT EXISTS / CREATE OR REPLACE): seguro rodar tanto
-- num banco vazio quanto num banco de producao ja povoado -- por isso NAO
-- precisa de `yoyo mark` no primeiro deploy contra a base existente.
--
-- Dialeto MySQL 8. A migracao para PostgreSQL (issue #115) reescreve este arquivo.
-- Politica so-aditiva de schema (#78): as migracoes seguintes nunca dao DROP.

SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE IF NOT EXISTS `animais` (
  `id` int NOT NULL AUTO_INCREMENT,
  `brinco` varchar(50) NOT NULL,
  `sexo` char(1) NOT NULL,
  `raca` varchar(100) DEFAULT NULL,
  `data_compra` date DEFAULT NULL,
  `preco_compra` decimal(10,2) DEFAULT NULL,
  `data_venda` date DEFAULT NULL,
  `preco_venda` decimal(10,2) DEFAULT NULL,
  `user_id` int NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `lote_id` int DEFAULT NULL,
  `pai_id` int DEFAULT NULL,
  `mae_id` int DEFAULT NULL,
  `data_nascimento` date DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_brinco_user` (`brinco`,`user_id`),
  KEY `idx_animais_venda` (`user_id`,`data_venda`),
  KEY `idx_animais_ativo` (`user_id`,`deleted_at`),
  KEY `idx_animais_ativo_venda` (`user_id`,`deleted_at`,`data_venda`),
  KEY `idx_animais_brinco` (`user_id`,`deleted_at`,`brinco`),
  KEY `idx_animais_lote` (`lote_id`,`deleted_at`),
  KEY `idx_animais_raca` (`user_id`,`raca`,`deleted_at`),
  KEY `idx_animais_pai` (`pai_id`),
  KEY `idx_animais_mae` (`mae_id`),
  CONSTRAINT `animais_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `usuarios` (`id`),
  CONSTRAINT `fk_animais_lote` FOREIGN KEY (`lote_id`) REFERENCES `lotes` (`id`),
  CONSTRAINT `fk_animais_mae` FOREIGN KEY (`mae_id`) REFERENCES `animais` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_animais_pai` FOREIGN KEY (`pai_id`) REFERENCES `animais` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `configuracoes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `nome_fazenda` varchar(100) DEFAULT NULL,
  `cidade_estado` varchar(100) DEFAULT NULL,
  `area_total` decimal(10,2) DEFAULT NULL,
  `gmd_meta` decimal(5,3) NOT NULL DEFAULT '0.800',
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`),
  CONSTRAINT `configuracoes_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `usuarios` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `cost_centers` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nome` varchar(50) NOT NULL,
  `categoria` varchar(20) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_nome_cat` (`nome`,`categoria`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `custos_operacionais` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `categoria` varchar(20) NOT NULL,
  `tipo_custo` varchar(50) NOT NULL,
  `valor` decimal(10,2) NOT NULL,
  `data_custo` date NOT NULL,
  `descricao` text,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_custos_busca` (`user_id`,`data_custo`),
  KEY `idx_custos_user_del_data` (`user_id`,`deleted_at`,`data_custo`),
  CONSTRAINT `custos_operacionais_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `usuarios` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `estoque_movimentacoes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `produto_id` int NOT NULL,
  `tipo` enum('entrada','saida') NOT NULL,
  `quantidade` decimal(10,3) NOT NULL,
  `custo_unitario` decimal(10,2) DEFAULT NULL,
  `motivo` varchar(300) DEFAULT NULL,
  `lote_fabricante` varchar(100) DEFAULT NULL,
  `data_validade` date DEFAULT NULL,
  `data_mov` date NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `idx_estoque_mov_produto` (`produto_id`,`user_id`),
  CONSTRAINT `estoque_movimentacoes_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `usuarios` (`id`),
  CONSTRAINT `estoque_movimentacoes_ibfk_2` FOREIGN KEY (`produto_id`) REFERENCES `estoque_produtos` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `estoque_produtos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `nome` varchar(200) NOT NULL,
  `unidade` varchar(50) NOT NULL,
  `categoria` enum('medicamento','vacina','suplemento','mineral','outro') NOT NULL DEFAULT 'outro',
  `estoque_minimo` decimal(10,3) NOT NULL DEFAULT '0.000',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `estoque_produtos_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `usuarios` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `financial_schedule` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `descricao` varchar(255) NOT NULL,
  `valor` decimal(10,2) NOT NULL,
  `vencimento` date NOT NULL,
  `status` varchar(20) DEFAULT 'pendente',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_financial_schedule_agenda` (`user_id`,`deleted_at`,`vencimento`),
  CONSTRAINT `financial_schedule_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `usuarios` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `lotes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `codigo_lote` varchar(50) NOT NULL,
  `descricao` varchar(200) DEFAULT NULL,
  `data_aquisicao` date NOT NULL,
  `custo_medio_cabeca` decimal(10,2) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `lotes_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `usuarios` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `medicacoes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `animal_id` int NOT NULL,
  `data_aplicacao` date NOT NULL,
  `nome_medicamento` varchar(100) NOT NULL,
  `custo` decimal(10,2) DEFAULT NULL,
  `observacoes` text,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_med_busca` (`animal_id`,`data_aplicacao`),
  CONSTRAINT `medicacoes_ibfk_1` FOREIGN KEY (`animal_id`) REFERENCES `animais` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `modulos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `pasto_id` int NOT NULL,
  `user_id` int NOT NULL,
  `nome` varchar(100) NOT NULL,
  `area_hectares` decimal(10,2) DEFAULT NULL,
  `capacidade_ua` decimal(10,2) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `idx_modulos_pasto` (`pasto_id`),
  CONSTRAINT `modulos_ibfk_1` FOREIGN KEY (`pasto_id`) REFERENCES `pastos` (`id`) ON DELETE CASCADE,
  CONSTRAINT `modulos_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `usuarios` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `ocupacao_animais` (
  `id` int NOT NULL AUTO_INCREMENT,
  `ocupacao_id` int NOT NULL,
  `animal_id` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `animal_id` (`animal_id`),
  KEY `idx_ocupacao_animais_oc` (`ocupacao_id`),
  CONSTRAINT `ocupacao_animais_ibfk_1` FOREIGN KEY (`ocupacao_id`) REFERENCES `ocupacoes` (`id`) ON DELETE CASCADE,
  CONSTRAINT `ocupacao_animais_ibfk_2` FOREIGN KEY (`animal_id`) REFERENCES `animais` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `ocupacoes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `modulo_id` int NOT NULL,
  `user_id` int NOT NULL,
  `data_entrada` date NOT NULL,
  `data_saida` date DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `idx_ocupacoes_modulo` (`modulo_id`),
  CONSTRAINT `ocupacoes_ibfk_1` FOREIGN KEY (`modulo_id`) REFERENCES `modulos` (`id`) ON DELETE CASCADE,
  CONSTRAINT `ocupacoes_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `usuarios` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `password_reset_tokens` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `code` char(6) NOT NULL,
  `expires_at` datetime NOT NULL,
  `used` tinyint(1) DEFAULT '0',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `password_reset_tokens_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `usuarios` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `pastos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `nome` varchar(100) NOT NULL,
  `area_hectares` decimal(10,2) DEFAULT NULL,
  `forrageira` varchar(100) DEFAULT NULL,
  `capacidade_ua` decimal(10,2) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `pastos_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `usuarios` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `pesagens` (
  `id` int NOT NULL AUTO_INCREMENT,
  `animal_id` int NOT NULL,
  `data_pesagem` date NOT NULL,
  `peso` decimal(10,2) NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_pesagens_otimizada` (`animal_id`,`data_pesagem`),
  KEY `idx_pesagens_max` (`animal_id`,`id` DESC),
  CONSTRAINT `pesagens_ibfk_1` FOREIGN KEY (`animal_id`) REFERENCES `animais` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `protocolos_sanitarios` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `nome` varchar(200) NOT NULL,
  `descricao` text,
  `intervalo_dias` int NOT NULL,
  `proxima_aplicacao` date NOT NULL,
  `ativo` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_sanitario_agenda` (`user_id`,`proxima_aplicacao`,`ativo`),
  CONSTRAINT `protocolos_sanitarios_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `usuarios` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `reproducao` (
  `id` int NOT NULL AUTO_INCREMENT,
  `vaca_id` int NOT NULL,
  `touro_id` int DEFAULT NULL,
  `touro_externo` varchar(200) DEFAULT NULL,
  `data_cobertura` date NOT NULL,
  `diagnostico` enum('pendente','positivo','negativo') DEFAULT 'pendente',
  `data_diagnostico` date DEFAULT NULL,
  `data_parto_prevista` date DEFAULT NULL,
  `data_parto` date DEFAULT NULL,
  `resultado` enum('vivo','natimorto','aborto') NOT NULL,
  `user_id` int NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `touro_id` (`touro_id`),
  KEY `idx_reproducao_vaca` (`vaca_id`),
  KEY `idx_reproducao_user` (`user_id`,`data_parto_prevista`),
  CONSTRAINT `reproducao_ibfk_1` FOREIGN KEY (`vaca_id`) REFERENCES `animais` (`id`) ON DELETE CASCADE,
  CONSTRAINT `reproducao_ibfk_2` FOREIGN KEY (`touro_id`) REFERENCES `animais` (`id`) ON DELETE SET NULL,
  CONSTRAINT `reproducao_ibfk_3` FOREIGN KEY (`user_id`) REFERENCES `usuarios` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `usuarios` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `email` varchar(255) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- Views: calculo pesado (GMD, fluxo de caixa, P&L, ocupacao) delegado ao banco.

CREATE OR REPLACE VIEW `v_gmd_analitico` AS with `pesagensordenadas` as (select `pesagens`.`animal_id` AS `animal_id`,`pesagens`.`data_pesagem` AS `data_pesagem`,`pesagens`.`peso` AS `peso`,row_number() OVER (PARTITION BY `pesagens`.`animal_id` ORDER BY `pesagens`.`data_pesagem` )  AS `rn_asc`,row_number() OVER (PARTITION BY `pesagens`.`animal_id` ORDER BY `pesagens`.`data_pesagem` desc )  AS `rn_desc` from `pesagens` where (`pesagens`.`deleted_at` is null)), `primeiraultima` as (select `pesagensordenadas`.`animal_id` AS `animal_id`,max((case when (`pesagensordenadas`.`rn_asc` = 1) then `pesagensordenadas`.`data_pesagem` end)) AS `data_inicial`,max((case when (`pesagensordenadas`.`rn_asc` = 1) then `pesagensordenadas`.`peso` end)) AS `peso_inicial`,max((case when (`pesagensordenadas`.`rn_desc` = 1) then `pesagensordenadas`.`data_pesagem` end)) AS `data_final`,max((case when (`pesagensordenadas`.`rn_desc` = 1) then `pesagensordenadas`.`peso` end)) AS `peso_final` from `pesagensordenadas` group by `pesagensordenadas`.`animal_id`) select `a`.`user_id` AS `user_id`,`a`.`id` AS `animal_id`,`a`.`brinco` AS `brinco`,`p`.`peso_final` AS `peso_final`,(`p`.`peso_final` - `p`.`peso_inicial`) AS `ganho_total`,(to_days(`p`.`data_final`) - to_days(`p`.`data_inicial`)) AS `dias`,(case when ((to_days(`p`.`data_final`) - to_days(`p`.`data_inicial`)) > 0) then ((`p`.`peso_final` - `p`.`peso_inicial`) / (to_days(`p`.`data_final`) - to_days(`p`.`data_inicial`))) else 0 end) AS `gmd` from (`primeiraultima` `p` join `animais` `a` on((`p`.`animal_id` = `a`.`id`))) where ((`p`.`data_inicial` <> `p`.`data_final`) and (`a`.`deleted_at` is null));

CREATE OR REPLACE VIEW `v_fluxo_caixa` AS select `uniao_geral`.`user_id` AS `user_id`,`uniao_geral`.`ano` AS `ano`,sum(`uniao_geral`.`receita`) AS `total_entradas`,sum(`uniao_geral`.`despesa_compra`) AS `total_compras`,sum(`uniao_geral`.`despesa_med`) AS `total_med`,sum(`uniao_geral`.`despesa_ops`) AS `total_ops` from (select `animais`.`user_id` AS `user_id`,year(`animais`.`data_venda`) AS `ano`,`animais`.`preco_venda` AS `receita`,0 AS `despesa_compra`,0 AS `despesa_med`,0 AS `despesa_ops` from `animais` where ((`animais`.`data_venda` is not null) and (`animais`.`deleted_at` is null)) union all select `animais`.`user_id` AS `user_id`,year(`animais`.`data_compra`) AS `ano`,0 AS `0`,`animais`.`preco_compra` AS `preco_compra`,0 AS `0`,0 AS `0` from `animais` where ((`animais`.`deleted_at` is null) and (`animais`.`data_compra` is not null)) union all select `a`.`user_id` AS `user_id`,year(`m`.`data_aplicacao`) AS `ano`,0 AS `0`,0 AS `0`,`m`.`custo` AS `custo`,0 AS `0` from (`medicacoes` `m` join `animais` `a` on((`m`.`animal_id` = `a`.`id`))) where ((`m`.`deleted_at` is null) and (`a`.`deleted_at` is null)) union all select `custos_operacionais`.`user_id` AS `user_id`,year(`custos_operacionais`.`data_custo`) AS `ano`,0 AS `0`,0 AS `0`,0 AS `0`,`custos_operacionais`.`valor` AS `valor` from `custos_operacionais` where (`custos_operacionais`.`deleted_at` is null)) `uniao_geral` group by `uniao_geral`.`user_id`,`uniao_geral`.`ano`;

CREATE OR REPLACE VIEW `vw_resultado_lote` AS select `l`.`id` AS `lote_id`,`l`.`user_id` AS `user_id`,`l`.`codigo_lote` AS `codigo_lote`,`l`.`descricao` AS `descricao`,`l`.`data_aquisicao` AS `data_aquisicao`,count(`a`.`id`) AS `total_animais`,coalesce(sum(`a`.`preco_compra`),0) AS `custo_aquisicao`,coalesce(sum((case when (`a`.`data_venda` is not null) then `a`.`preco_venda` end)),0) AS `receita_vendas`,coalesce(sum(`med`.`custo_med`),0) AS `custo_medicacoes`,count((case when (`a`.`data_venda` is not null) then 1 end)) AS `animais_vendidos`,((coalesce(sum((case when (`a`.`data_venda` is not null) then `a`.`preco_venda` end)),0) - coalesce(sum(`a`.`preco_compra`),0)) - coalesce(sum(`med`.`custo_med`),0)) AS `margem_bruta` from ((`lotes` `l` join `animais` `a` on(((`a`.`lote_id` = `l`.`id`) and (`a`.`deleted_at` is null)))) left join (select `medicacoes`.`animal_id` AS `animal_id`,sum(`medicacoes`.`custo`) AS `custo_med` from `medicacoes` where (`medicacoes`.`deleted_at` is null) group by `medicacoes`.`animal_id`) `med` on((`med`.`animal_id` = `a`.`id`))) where (`l`.`deleted_at` is null) group by `l`.`id`,`l`.`user_id`,`l`.`codigo_lote`,`l`.`descricao`,`l`.`data_aquisicao`;

CREATE OR REPLACE VIEW `vw_saldo_estoque` AS select `p`.`id` AS `produto_id`,`p`.`user_id` AS `user_id`,`p`.`nome` AS `nome`,`p`.`unidade` AS `unidade`,`p`.`categoria` AS `categoria`,`p`.`estoque_minimo` AS `estoque_minimo`,coalesce(sum((case when (`m`.`tipo` = 'entrada') then `m`.`quantidade` else 0 end)),0) AS `total_entradas`,coalesce(sum((case when (`m`.`tipo` = 'saida') then `m`.`quantidade` else 0 end)),0) AS `total_saidas`,coalesce(sum((case when (`m`.`tipo` = 'entrada') then `m`.`quantidade` else -(`m`.`quantidade`) end)),0) AS `saldo_atual`,(case when (coalesce(sum((case when (`m`.`tipo` = 'entrada') then `m`.`quantidade` else -(`m`.`quantidade`) end)),0) < `p`.`estoque_minimo`) then 1 else 0 end) AS `abaixo_minimo`,min((case when ((`m`.`tipo` = 'entrada') and (`m`.`data_validade` is not null)) then `m`.`data_validade` end)) AS `proxima_validade`,(case when (min((case when ((`m`.`tipo` = 'entrada') and (`m`.`data_validade` is not null)) then `m`.`data_validade` end)) < curdate()) then 1 else 0 end) AS `tem_vencido` from (`estoque_produtos` `p` left join `estoque_movimentacoes` `m` on((`m`.`produto_id` = `p`.`id`))) group by `p`.`id`,`p`.`user_id`,`p`.`nome`,`p`.`unidade`,`p`.`categoria`,`p`.`estoque_minimo`;

CREATE OR REPLACE VIEW `vw_ocupacao_atual` AS select `m`.`id` AS `modulo_id`,`m`.`pasto_id` AS `pasto_id`,`m`.`user_id` AS `user_id`,`m`.`nome` AS `modulo_nome`,`m`.`capacidade_ua` AS `capacidade_ua`,`o`.`id` AS `ocupacao_id`,`o`.`data_entrada` AS `data_entrada`,count(`oa`.`animal_id`) AS `ua_atual`,round(((count(`oa`.`animal_id`) / nullif(`m`.`capacidade_ua`,0)) * 100),1) AS `pct_lotacao` from ((`modulos` `m` join `ocupacoes` `o` on(((`o`.`modulo_id` = `m`.`id`) and (`o`.`data_saida` is null)))) join `ocupacao_animais` `oa` on((`oa`.`ocupacao_id` = `o`.`id`))) group by `m`.`id`,`m`.`pasto_id`,`m`.`user_id`,`m`.`nome`,`m`.`capacidade_ua`,`o`.`id`,`o`.`data_entrada`;

CREATE OR REPLACE VIEW `vw_dias_descanso` AS select `m`.`id` AS `modulo_id`,`m`.`pasto_id` AS `pasto_id`,`m`.`user_id` AS `user_id`,`m`.`nome` AS `modulo_nome`,max(`o`.`data_saida`) AS `ultima_saida`,(to_days(curdate()) - to_days(max(`o`.`data_saida`))) AS `dias_descanso` from (`modulos` `m` left join `ocupacoes` `o` on(((`o`.`modulo_id` = `m`.`id`) and (`o`.`data_saida` is not null)))) where `m`.`id` in (select `ocupacoes`.`modulo_id` from `ocupacoes` where (`ocupacoes`.`data_saida` is null)) is false group by `m`.`id`,`m`.`pasto_id`,`m`.`user_id`,`m`.`nome`;

CREATE OR REPLACE VIEW `vw_gmd_por_modulo` AS with `oa_rel` as (select `o`.`modulo_id` AS `modulo_id`,`m`.`nome` AS `modulo_nome`,`m`.`pasto_id` AS `pasto_id`,`m`.`user_id` AS `user_id`,`oa`.`animal_id` AS `animal_id` from ((`ocupacoes` `o` join `ocupacao_animais` `oa` on((`oa`.`ocupacao_id` = `o`.`id`))) join `modulos` `m` on((`m`.`id` = `o`.`modulo_id`)))), `po` as (select `p`.`animal_id` AS `animal_id`,`p`.`data_pesagem` AS `data_pesagem`,`p`.`peso` AS `peso`,row_number() OVER (PARTITION BY `p`.`animal_id` ORDER BY `p`.`data_pesagem` )  AS `rn_asc`,row_number() OVER (PARTITION BY `p`.`animal_id` ORDER BY `p`.`data_pesagem` desc )  AS `rn_desc` from (`pesagens` `p` join `oa_rel` `r` on((`r`.`animal_id` = `p`.`animal_id`))) where (`p`.`deleted_at` is null)), `pu` as (select `po`.`animal_id` AS `animal_id`,max((case when (`po`.`rn_asc` = 1) then `po`.`data_pesagem` end)) AS `data_ini`,max((case when (`po`.`rn_asc` = 1) then `po`.`peso` end)) AS `peso_ini`,max((case when (`po`.`rn_desc` = 1) then `po`.`data_pesagem` end)) AS `data_fim`,max((case when (`po`.`rn_desc` = 1) then `po`.`peso` end)) AS `peso_fim` from `po` group by `po`.`animal_id`), `gmd_calc` as (select `pu`.`animal_id` AS `animal_id`,(case when ((to_days(`pu`.`data_fim`) - to_days(`pu`.`data_ini`)) > 0) then ((`pu`.`peso_fim` - `pu`.`peso_ini`) / (to_days(`pu`.`data_fim`) - to_days(`pu`.`data_ini`))) else NULL end) AS `gmd` from `pu` where (`pu`.`data_ini` <> `pu`.`data_fim`)) select `r`.`modulo_id` AS `modulo_id`,`r`.`modulo_nome` AS `modulo_nome`,`r`.`pasto_id` AS `pasto_id`,`r`.`user_id` AS `user_id`,count(distinct `r`.`animal_id`) AS `qtd_animais`,round(avg(`g`.`gmd`),3) AS `gmd_medio` from (`oa_rel` `r` left join `gmd_calc` `g` on((`g`.`animal_id` = `r`.`animal_id`))) group by `r`.`modulo_id`,`r`.`modulo_nome`,`r`.`pasto_id`,`r`.`user_id`;

CREATE OR REPLACE VIEW `vw_historico_vaca` AS select `r`.`vaca_id` AS `vaca_id`,`a`.`user_id` AS `user_id`,count(0) AS `total_coberturas`,sum((case when (`r`.`resultado` = 'vivo') then 1 else 0 end)) AS `partos_vivos`,round(((sum((case when (`r`.`resultado` = 'vivo') then 1 else 0 end)) / count(0)) * 100),1) AS `taxa_sucesso`,min(`r`.`data_cobertura`) AS `primeira_cobertura`,max(`r`.`data_cobertura`) AS `ultima_cobertura` from (`reproducao` `r` join `animais` `a` on((`r`.`vaca_id` = `a`.`id`))) group by `r`.`vaca_id`,`a`.`user_id`;

CREATE OR REPLACE VIEW `vw_partos_previstos` AS select `r`.`id` AS `id`,`r`.`user_id` AS `user_id`,`r`.`vaca_id` AS `vaca_id`,`v`.`brinco` AS `vaca_brinco`,`r`.`data_cobertura` AS `data_cobertura`,`r`.`data_parto_prevista` AS `data_parto_prevista`,`r`.`diagnostico` AS `diagnostico`,(to_days(`r`.`data_parto_prevista`) - to_days(curdate())) AS `dias_restantes` from (`reproducao` `r` join `animais` `v` on(((`r`.`vaca_id` = `v`.`id`) and (`v`.`deleted_at` is null)))) where ((`r`.`diagnostico` = 'positivo') and (`r`.`data_parto` is null) and (`r`.`data_parto_prevista` is not null));

SET FOREIGN_KEY_CHECKS = 1;
