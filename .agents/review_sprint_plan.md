# Plano de Revisão e Melhorias — Sistema de Gestão de Gado

**Atualizado em:** 2026-06-30

---

## Status das Sprints

| Sprint | Escopo | Status |
|--------|--------|--------|
| Sprint 1 | Bugs críticos (datas, ranking touros, margem painel animal) | ✅ Concluído |
| Sprint 2 | Widgets de prenhez e GMD por módulo no painel financeiro | ✅ Concluído |
| Sprint 3 | Agrupamento de custos por (data, categoria, tipo) | ✅ Concluído |
| Sprint 4 | Venda coletiva com cálculo por arroba | ✅ Concluído |
| Sprint 5 | Filtro "Nascidos na Fazenda" no painel | ✅ Concluído |
| Sprint 6 | GMD meta configurável pelo proprietário | ✅ Concluído |
| Sprint 7 | Painel de Compra/Venda unificado (UX/UI) | ✅ Concluído |
| Bug 7.0 | Margem interna do painel de dados/genealogia em /animal | ✅ Concluído |

---

## Diagnóstico Original (Sprints 1–3) — Arquivo Histórico

As três primeiras sprints foram implementadas no commit `0948eaa` (Sprint 1), `c9a88de` (Sprint 2) e `529f25b` (Sprint 3). Detalhes de implementação mantidos abaixo para referência.

<details>
<summary>Ver diagnóstico e tarefas originais (Sprints 1–3)</summary>

### Bug 1 — Ranking de Touros: Internal Server Error
**Arquivo:** `routes/operacional.py:544` → `repositories/animal_repository.py:471`

A query em `get_ranking_touros` é uma CTE com `ROW_NUMBER()`. `get_gmd_medio_rebanho` retornava `None` quando não há pesagens; template `ranking_touros.html` aplicava filtro `|brl` sobre `None` sem guard. **Resolvido em Sprint 1.**

### Bug 2 — Margem no Painel Lateral Direito da Página de Animal
**Arquivo:** `static/css/design_system.css:872`

Grid `1fr 300px` sem `minmax(0)` na coluna esquerda e sem padding nos cards internos do painel direito. **Corrigido em Sprint 1** — ver Bug 7.0 para issue residual de padding interno.

### Bug 3 — Datas Sem Formato Brasileiro
Filtro `|date_br` adicionado em `app.py` e aplicado em todos os templates. **Resolvido em Sprint 1.**

### Melhoria 4 — Widget de Prenhez no Painel de Relatórios
`get_partos_previstos` e `vw_partos_previstos` já existiam; widget adicionado em `financeiro.html`. **Implementado em Sprint 2.**

### Melhoria 5 — Widget de GMD por Módulo
Top-5 módulos por GMD exibido no painel financeiro via `get_top_gmd_por_modulo`. **Implementado em Sprint 2.**

### Melhoria 6 — Agrupamento de Custos
`get_custos_por_ano` passou de 5 para 6 colunas (acrescentou `n` para contagem); template exibe `Tipo (3x)`. Export CSV atualizado. **Implementado em Sprint 3.**

</details>

---

## Sprint 4 — Venda Coletiva (2–3 dias)

### Problema
A venda é sempre animal a animal via `/vender/<id_animal>`. Na prática o produtor negocia um lote inteiro com o frigorífico de uma vez, informando um único preço de arroba para todos os animais.

### Estado atual
- `animal_repository.registrar_venda(animal_id, user_id, data_venda, preco_venda, peso_venda)` — individual, linha 583
- Rota `/vender/<id_animal>` em `routes/operacional.py:158` — individual
- Cálculo: `preco_venda = (peso / 30) * valor_arroba` (1 arroba vivo = 30 kg) — mesmo padrão usado no cadastro

### Implementação

#### 4.1 — Repositório (`repositories/animal_repository.py`)

Adicionar `registrar_venda_lote(animais_data, user_id)` reutilizando a lógica de `registrar_venda`:

```python
def registrar_venda_lote(animais_data: list[dict], user_id: int) -> int:
    """
    animais_data = [{'animal_id': int, 'data_venda': str, 'peso_venda': float, 'preco_venda': float}, ...]
    Executa tudo dentro de uma única transação. Retorna quantidade de animais vendidos.
    """
    vendidos = 0
    with get_db_cursor() as cursor:
        for item in animais_data:
            cursor.execute(
                "SELECT id FROM animais WHERE id = %s AND user_id = %s "
                "AND data_venda IS NULL AND deleted_at IS NULL",
                (item['animal_id'], user_id)
            )
            if not cursor.fetchone():
                continue
            cursor.execute(
                "UPDATE animais SET data_venda = %s, preco_venda = %s WHERE id = %s",
                (item['data_venda'], item['preco_venda'], item['animal_id'])
            )
            cursor.execute(
                "INSERT INTO pesagens (animal_id, data_pesagem, peso_kg) VALUES (%s, %s, %s)",
                (item['animal_id'], item['data_venda'], item['peso_venda'])
            )
            vendidos += 1
    return vendidos
```

#### 4.2 — Rota (`routes/operacional.py`)

```python
@operacional_bp.route('/venda-lote', methods=['GET', 'POST'])
@login_required
def venda_lote():
    if request.method == 'POST':
        errors = validate(request.form, [
            ('data_venda',    {'required': True, 'type': 'date',  'label': 'Data de venda'}),
            ('valor_arroba',  {'required': True, 'type': 'float', 'min_val': 0.01, 'label': 'Valor da @'}),
        ])
        if errors:
            animais = animal_repository.get_animais_ativos(current_user.id)
            return render_template('venda_lote.html', animais=animais, mensagem=errors[0]), 400

        animal_ids = request.form.getlist('animal_ids[]')
        pesos      = request.form.getlist('pesos_venda[]')
        data_venda = request.form['data_venda']
        val_arr    = float(request.form['valor_arroba'])

        if not animal_ids:
            # ... mensagem de erro: nenhum animal selecionado
            ...

        animais_data = []
        for aid, peso_str in zip(animal_ids, pesos):
            peso = float(peso_str)
            animais_data.append({
                'animal_id':   int(aid),
                'data_venda':  data_venda,
                'peso_venda':  peso,
                'preco_venda': round((peso / 30) * val_arr, 2),
            })

        vendidos = animal_repository.registrar_venda_lote(animais_data, current_user.id)
        flash(f'{vendidos} animais vendidos com sucesso.')
        return redirect(url_for('operacional.painel'))

    animais = animal_repository.get_animais_ativos(current_user.id)
    return render_template('venda_lote.html', animais=animais)
```

#### 4.3 — Template (`templates/venda_lote.html`)

Estrutura da tabela:

| Sel | Brinco | Raça | Último Peso (kg) | Peso de Venda (kg) | Valor Estimado |
|-----|--------|------|-------------------|--------------------|----------------|
| ☐  | 001    | Nelore | 420 kg          | `<input>` pré-preenchido | R$ calculado via JS |

- Campo global: `data_venda` + `valor_arroba`
- JS: ao digitar em qualquer `peso_venda` ou `valor_arroba`, recalcular `valor_estimado = (peso/30)*arroba` em tempo real
- Rodapé da tabela: somatório de animais selecionados + kg total + R$ total estimado
- Validação JS antes do submit: pelo menos 1 animal marcado + peso preenchido para cada marcado

#### 4.4 — Testes

- `tests/test_venda_lote.py`:
  - POST com 3 animais válidos → 3 registros atualizados, 3 pesagens inseridas
  - POST com animal_id inválido (outro user) → ignorado silenciosamente, contador = 0
  - POST sem animal_ids → retorna 400 com mensagem

---

## Sprint 5 — Filtro "Nascidos na Fazenda" no Painel (1 dia)

### Problema
Não há como distinguir no painel animais nascidos na própria fazenda de animais comprados. Importante para rastrear eficiência reprodutiva e separar custo de aquisição de custo de criação.

### Sinal de origem
- **Nascido na fazenda:** `data_compra IS NULL AND data_nascimento IS NOT NULL`
- **Comprado:** `data_compra IS NOT NULL`
- Esta convenção já existe na rota de cadastro (`routes/operacional.py:89`): "Informe a data de compra (animal comprado) ou a data de nascimento (nascido na fazenda)"

### Implementação

#### 5.1 — Repositório (`repositories/animal_repository.py`)

Em `get_animais_paginados(user_id, status, pagina, por_pagina, raca, busca)`, adicionar parâmetro `origem: str = None`:

```python
if origem == 'fazenda':
    conds.append("a.data_compra IS NULL AND a.data_nascimento IS NOT NULL")
```

O parâmetro `origem` combina com `status` — é possível ver "nascidos na fazenda ativos" e "nascidos na fazenda vendidos" simultaneamente.

#### 5.2 — Rota (`routes/operacional.py` → `painel()`)

```python
origem = request.args.get('origem', '')  # '' | 'fazenda'
animais, total = animal_repository.get_animais_paginados(
    current_user.id, status, pagina, POR_PAGINA, raca, busca, origem=origem
)
```

Passar `origem` ao template para marcar o botão/tab como ativo.

#### 5.3 — Template (`templates/index.html`)

Adicionar ao seletor de filtros existente (ao lado de Ativos/Vendidos):

```html
<a href="?status={{ status }}&origem=fazenda{{ '&raca=' + raca if raca }}"
   class="btn btn-sm {% if origem == 'fazenda' %}btn-primary{% else %}btn-ghost{% endif %}">
  Nascidos na Fazenda
</a>
```

Quando `origem=fazenda` está ativo, exibir badge de contagem no botão.

#### 5.4 — Testes

- GET `/painel?origem=fazenda` retorna apenas animais com `data_compra IS NULL AND data_nascimento IS NOT NULL`
- Combinar com `status=vendido` retorna nascidos na fazenda que já foram vendidos

---

## Sprint 6 — GMD Meta Configurável (2 dias)

### Problema
A referência de 0.800 kg/dia está hardcoded em 4+ lugares no template `animal_progenie.html`. Cada fazenda tem uma meta diferente dependendo da raça, manejo e mercado-alvo. O hardcode impede análise personalizada.

### Ocorrências hardcoded a eliminar

| Arquivo | Linha | Contexto |
|---------|-------|---------|
| `templates/animal_progenie.html` | 28 | Label "Linha tracejada = referência 0.800 kg/dia" |
| `templates/animal_progenie.html` | 64 | `if gmd >= 0.8 ... elif gmd >= 0.6` (cor da célula) |
| `templates/animal_progenie.html` | 157 | `{ yAxis: 0.8, name: 'Meta' }` |
| `templates/animal_progenie.html` | 170–171 | Chart markline + label "Ref. 0.800" |

### Implementação

#### 6.1 — Banco (`init_db.py`)

```sql
-- Proteger com INFORMATION_SCHEMA antes de executar
ALTER TABLE configuracoes
  ADD COLUMN gmd_meta DECIMAL(5,3) NOT NULL DEFAULT 0.800;
```

#### 6.2 — Repositório (`repositories/configuracao_repository.py`)

- `get_configuracao()`: adicionar `gmd_meta` no SELECT
- `salvar_configuracao()`: aceitar e persistir `gmd_meta`

#### 6.3 — Context Processor (`app.py`)

```python
@app.context_processor
def inject_globals():
    gmd_meta = 0.800
    if current_user.is_authenticated:
        cfg = configuracao_repository.get_configuracao(current_user.id)
        if cfg and cfg.get('gmd_meta'):
            gmd_meta = float(cfg['gmd_meta'])
    return dict(
        nome_fazenda_header=...,  # existente
        gmd_meta=gmd_meta,
    )
```

Assim `gmd_meta` fica disponível em todos os templates sem precisar passar via rota.

#### 6.4 — Rota de Configurações (`routes/configuracoes.py`)

Adicionar ao form de configurações existente:

```python
errors = validate(request.form, [
    ...,  # campos existentes
    ('gmd_meta', {'required': False, 'type': 'float', 'min_val': 0.1, 'max_val': 5.0, 'label': 'GMD Meta (kg/dia)'}),
])
```

#### 6.5 — Templates

**`templates/animal_progenie.html`** — substituir todas as ocorrências hardcoded:

```jinja
{# linha 28 #}
Linha tracejada = referência {{ "%.3f"|format(gmd_meta) }} kg/dia

{# linha 64 — limite inferior = 75% da meta #}
{% set gmd_limite = (gmd_meta * 0.75) | round(3) %}
color: {% if gmd >= gmd_meta %}var(--color-primary){% elif gmd >= gmd_limite %}var(--color-accent-dark){% else %}var(--color-danger){% endif %}

{# linha 157 — chart markline #}
data: [{ yAxis: {{ gmd_meta }}, name: 'Meta' }]

{# linha 170–171 — label #}
data: [{ yAxis: {{ gmd_meta }} }],
label: { formatter: 'Ref. {{ "%.3f"|format(gmd_meta) }}', color: '#9B9B99', fontSize: 10 }
```

**`templates/configuracoes.html`** — adicionar campo:

```html
<div class="form-group">
  <label class="form-label" for="gmd_meta">GMD Meta (kg/dia)</label>
  <input type="number" id="gmd_meta" name="gmd_meta" class="form-input"
         step="0.001" min="0.1" max="5" value="{{ config.gmd_meta or '0.800' }}">
  <p class="form-hint">Referência usada para colorir e plotar a linha de meta nos gráficos de progênie.</p>
</div>
```

#### 6.6 — Função de Outliers por Meta (opcional, baixo custo)

Adicionar em `animal_repository.py`:

```python
def get_animais_abaixo_gmd_meta(user_id, gmd_meta: float):
    """Animais ativos com GMD abaixo de (gmd_meta * 0.75) — limiar configurável."""
    limite = gmd_meta * 0.75
    with get_db_cursor() as cursor:
        cursor.execute(
            "WITH gmd_calc AS (...) "  # mesma CTE de get_animais_com_gmd
            "SELECT animal_id, brinco, gmd FROM gmd_calc "
            "WHERE gmd IS NOT NULL AND gmd < %s ORDER BY gmd ASC",
            (limite,)
        )
        return cursor.fetchall()
```

Expor no painel de relatórios como "Animais abaixo da meta (< 75% do GMD alvo)".

#### 6.7 — Testes

- `configuracoes` com `gmd_meta=1.200` → `animal_progenie.html` renderizado com `1.200` no label e chart
- `get_animais_abaixo_gmd_meta(user_id, 1.0)` retorna apenas animais com GMD < 0.75

---

## Sprint 7 — Painel de Compra/Venda Unificado (2 dias)

### Problema (avaliação UX/UI)

O fluxo atual tem os pontos de entrada de compra e venda distribuídos de forma pouco intuitiva:

| Ação | Entrada atual | Problema |
|------|---------------|---------|
| Comprar animal individual | Botão "Novo Animal" na nav | Nome genérico; não comunica intenção de compra |
| Comprar lote | Botão "Novo Lote" na nav | Separado do fluxo de compra; usuário não sabe qual usar |
| Importar CSV | Página isolada sem acesso na nav | Praticamente escondido |
| Vender animal | Botão na ficha individual do animal | Exige navegar até o animal para iniciar a venda |
| Venda coletiva | Não existe (Sprint 4) | — |

**Proposta:** remover os botões "Novo Animal" e "Novo Lote" da nav e substituir por um único botão **"Transações"** → `/transacoes` — hub que agrupa todas as operações de entrada e saída de animais.

### Implementação

#### 7.1 — Rota (`routes/operacional.py`)

```python
@operacional_bp.route('/transacoes')
@login_required
def transacoes():
    return render_template('transacoes.html')
```

#### 7.2 — Template (`templates/transacoes.html`)

Layout two-column:

```
┌─────────────────────────┬─────────────────────────┐
│    🐄  ENTRADAS          │    💰  SAÍDAS            │
│  ─────────────────────  │  ─────────────────────  │
│  [Animal Individual]    │  [Venda Coletiva]        │
│  Cadastrar um animal    │  Vender múltiplos animais│
│  comprado ou nascido    │  com valor por arroba    │
│                         │                          │
│  [Lote de Animais]      │  [Venda Individual]      │
│  Comprar vários animais │  Acessar via ficha do    │
│  de uma vez             │  animal                  │
│                         │                          │
│  [Importar CSV]         │                          │
│  Onboarding de rebanho  │                          │
│  existente via planilha │                          │
└─────────────────────────┴─────────────────────────┘
```

Cada card: ícone SVG + título + descrição de 1 linha + botão CTA.

#### 7.3 — Navegação (`templates/base.html`)

- Remover links "Novo Animal" e "Novo Lote" da navbar (ou do dropdown de ações)
- Adicionar "Transações" apontando para `/transacoes`
- Os endpoints `/cadastro`, `/cadastro-lote`, `/importar-csv` e `/venda-lote` continuam funcionando para deep-links e redirects pós-ação

#### 7.4 — Testes

- GET `/transacoes` retorna 200 com todos os 4 cards
- Links do `/transacoes` → `/cadastro`, `/cadastro-lote`, `/importar-csv`, `/venda-lote` retornam 200
- Nav não contém mais textos "Novo Animal" / "Novo Lote"

---

## Bug 7.0 — Margem Interna do Painel de Dados/Genealogia em `/animal`

### Problema
A Sprint 1.2 corrigiu o layout do grid (coluna direita colapsa em mobile). Porém os cards internos do painel direito (`Dados do Animal`, `Genealogia`) permanecem sem padding interno — conteúdo colado na borda do card.

### Investigação necessária
1. Abrir `templates/detalhes.html` e verificar se os cards internos usam a classe `.card` com `.card-body` ou têm divs sem classe de espaçamento
2. Se usam `.card-body` → verificar se `design_system.css` define padding para `.card-body` ou se foi omitido nesse bloco
3. Confirmar em viewport ≥ 900px (layout 2 colunas ativo)

### Correção esperada
Garantir que cada seção do painel direito (dados, genealogia) esteja dentro de `.card > .card-body` com `padding: var(--space-4)` mínimo. Se o template usa `<div class="card">` sem `.card-body`, adicionar o wrapper.

---

## Ordem de Execução Recomendada

```
Bug 7.0 (30 min — inspecionar + corrigir padding, baixo risco)
  ↓
Sprint 4 — Venda Coletiva (pré-requisito para Sprint 7)
  ↓
Sprint 5 — Filtro Nascidos na Fazenda (independente, 1 dia)
  ↓
Sprint 6 — GMD Meta (independente, 2 dias)
  ↓
Sprint 7 — Painel Transações (depende de Sprint 4 para o card de venda coletiva)
```

---

## Checklist de Testes por Tarefa

| Tarefa | Teste mínimo |
|--------|-------------|
| Bug 7.0 | `/animal/<id>` em viewport 900px+ — cards "Dados" e "Genealogia" com padding visível dos 4 lados |
| 4 (venda lote) | POST `/venda-lote` com 3 animais → 3 `data_venda` + 3 pesagens inseridas na transação |
| 4 (venda lote) | animal_id de outro usuário na lista → ignorado, não vendido |
| 4 (venda lote) | JS calcula `valor_estimado` corretamente: peso=450, arroba=320 → R$ 4.800,00 |
| 5 (nascidos) | GET `/painel?origem=fazenda` retorna apenas animais com `data_compra IS NULL` |
| 5 (nascidos) | Combinar `origem=fazenda&status=vendido` filtra corretamente |
| 6 (GMD meta) | Salvar `gmd_meta=1.200` em config → `/animal/<id>/progenie` exibe "Ref. 1.200" no gráfico |
| 6 (GMD meta) | `gmd_meta` padrão = 0.800 quando campo ausente no banco |
| 7 (transações) | GET `/transacoes` com todos os cards; nav sem "Novo Animal" e "Novo Lote" |
| 7 (transações) | Todos os CTAs da página redirecionam para a rota correta |
