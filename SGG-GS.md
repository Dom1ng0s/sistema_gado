# Roadmap — SGG & Gado-Scraper

---

## SGG (Sistema de Gestão de Gado)

### Fase 1 — Fundação *(não pule)*

Nenhuma feature nova antes dessa fase estar completa. O que vier depois depende disso.

**1. API REST**

Separar as rotas Flask em duas camadas via Blueprints:
- `/views` — rotas que servem templates HTML (comportamento atual)
- `/api/v1` — endpoints JSON para consumo externo

Não exige migração para FastAPI agora. O Gado-Scraper, o bot do Telegram e um eventual mobile vão consumir essa API — ela precisa existir antes.

**2. Segurança**

Quatro itens concretos, não "conferir segurança":
- Validação de input em todas as rotas que recebem dados (nunca confiar no frontend)
- Proteção CSRF nas rotas de formulário (Flask-WTF)
- Rate limiting nas rotas de API (Flask-Limiter)
- Auditoria do SQL puro escrito fora das Views — confirmar ausência de interpolação de string em queries

---

### Fase 2 — Features de Alto Valor

**3. Alertas de GMD**

A View de GMD já existe. O alerta é uma query que compara o GMD individual com a média do rebanho e expõe como endpoint `/api/v1/alertas/gmd`.

Valor direto para o pecuarista, esforço relativo baixo.

**4. Exportar PDF**

Com a API pronta, vira um endpoint `/api/v1/relatorio/pdf`.  
Usar a mesma abordagem do Polymorph: Playwright renderizando HTML via Jinja2 — padrão já conhecido.

---

### Fase 3 — Expansão de Domínio

As três features abaixo têm dependências entre si e com a Fase 1. Ordem importa.

**5. Gestão de Pastos (Pastejo Rotacionado)**

*Schema:*
- Tabela `pastos` — área total, tipo de forrageira, capacidade em UA/hectare
- Tabela `modulos` (filha de `pastos`) — área e capacidade do módulo
- Tabela `ocupacoes` — entrada e saída de lotes por módulo com data

*Views:*
- `vw_ocupacao_atual` — módulos ocupados vs. em descanso
- `vw_dias_descanso` — dias desde a última saída por módulo
- `vw_gmd_por_modulo` — cruzamento de GMD das pesagens com o módulo de ocupação no período

*Indicadores no dashboard:*
- UA/hectare atual vs. capacidade máxima (alerta de superlotação)
- Ranking de módulos por GMD produzido

**6. Hereditariedade Animal**

*6a. Migração do schema:*
- Adicionar `pai_id` e `mae_id` como FK nullable na tabela `animais` (relação auto-referencial)
- `pai_id` pode ser touro do rebanho ou referência externa (sêmen comprado)
- `mae_id` sempre uma vaca do rebanho
- Criar tabela `reproducao`: `vaca_id`, `touro_id`, `data_cobertura`, `data_parto`, `resultado` (vivo/natimorto/aborto)

*6b. Views de produtividade genética:*
- `vw_gmd_por_touro` — média de GMD dos filhos agrupada por `pai_id`
- `vw_historico_vaca` — contagem de partos, intervalo médio entre partos, taxa de sucesso por `mae_id`

*6c. Endpoints e telas:*
- Listagem de progênie por touro
- Histórico reprodutivo por vaca
- Ranking de touros por GMD médio da progênie

**7. Estoque Virtual de Insumos**

O objetivo é dar visibilidade de patrimônio imobilizado em insumos (vacinas, suplementos, ração), não controle de movimentação física detalhada.

*Lógica de dois momentos:*
- **Compra** → entrada no estoque virtual como ativo (dinheiro saiu do caixa, virou estoque)
- **Aplicação** → baixa automática do estoque + lançamento de despesa no fluxo de caixa

Como o controle de vacina por animal já existe no SGG, a aplicação conecta os dois: cada registro sanitário dispara o UPDATE no estoque e gera a despesa automaticamente — sem duplo lançamento pelo produtor.

*Schema:*
- Tabela `estoque_virtual`: `produto`, `quantidade_comprada`, `unidade`, `valor_unitario`, `data_compra`, `quantidade_atual`
- Tabela `categorias_despesa`: hierarquia de categoria pai + subcategoria (ex: Sanidade → Vacina; Nutrição → Suplemento Mineral)
- Lançamentos no fluxo de caixa ganham campo `categoria_id` opcional

*Views:*
- `vw_estoque_atual` — quantidade disponível e valor imobilizado por produto
- `vw_custos_por_categoria` — despesa agregada por categoria, por período e por animal

*Painel do produtor:*
- Quantidade em estoque por produto
- Valor imobilizado total
- Consumo médio mensal (base para projeção de reposição)

**8. UI/UX**

Por último, propositalmente. Revisar interface antes do schema estar estável e das features consolidadas garante retrabalho. Com a API pronta e os dados definidos, é possível saber exatamente o que cada tela precisa mostrar.

---

## Gado-Scraper

> **Pré-requisito:** A API REST do SGG (Fase 1) precisa estar no ar antes de iniciar os itens abaixo.

**Fase 1 — Resolver o problema estrutural**

**1. Migrar armazenamento histórico**

O modelo atual (git como banco histórico) tem teto técnico baixo: queries de série temporal são inviáveis, e o repositório cresce indefinidamente.

*Decisão de storage:* PostgreSQL com tabela `cotacoes` simples:
```
data | praca | tipo (boi/novilha) | valor
```

O GitHub Actions passa a fazer INSERT em vez de commit de JSON. O histórico atual no git pode ser importado via script único de migração.

**2. Bot de Telegram**

Independente do SGG. Lê diretamente o banco do Gado-Scraper e envia alertas de cotação.

Fluxo: GitHub Actions coleta cotação → salva no banco → bot lê o banco → envia alerta no Telegram.

*Funcionalidades iniciais:*
- Cotação do dia por praça escolhida pelo usuário
- Alerta quando o preço de uma praça-chave cruzar um threshold configurável

Aproveita o padrão já construído no Plin (Telegram Bot + SQLAlchemy).

**3. Dashboard de Histórico**

Com dados em banco, série temporal passa a ser consultável.

- **Opção rápida:** Streamlit para protótipo independente
- **Opção integrada:** nova rota no SGG consumindo a API — mais trabalho, mais coerente com o produto

*Indicadores prioritários:*
- Variação de preço por praça ao longo do tempo
- Comparação entre praças no mesmo período
- Média móvel para identificar tendência

---

## Ordem entre os dois projetos

```
SGG Fase 1 (API REST + Segurança)
    └── SGG Fase 2 (Alertas + PDF)
        └── SGG Fase 3 (Pastos, Hereditariedade, Estoque Virtual, UI/UX)

Gado-Scraper Fase 1 (Migração de storage)
    ├── Bot de Telegram (lê banco do Gado-Scraper diretamente)
    └── Dashboard de Histórico
```

O Gado-Scraper e o SGG são independentes entre si. A migração de storage do Gado-Scraper pode acontecer em paralelo com qualquer fase do SGG.
