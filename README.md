# Sistema de Gestão de Gado (SGG)

**ERP Zootécnico de alta performance para pecuária de corte**

Solução web para pecuaristas que precisam controlar rebanho, calcular **GMD (Ganho Médio Diário)**, gerenciar pastos, rastrear hereditariedade e acompanhar o **fluxo de caixa** da fazenda — tudo em um só lugar, com lógica de cálculo delegada ao banco de dados para máxima performance.

**Acesso online:** [sistemadogado.up.railway.app](https://sistemadogado.up.railway.app/)

---

## Capturas de Tela

| Dashboard Financeiro | Análise Zootécnica (GMD) | Analytics do Rebanho |
|---|---|---|
| ![Dashboard Financeiro](photos/financeiro.png) | ![Análise Zootécnica](photos/animal.png) | ![Analytics do Rebanho](photos/rebanho.png) |
| *Fluxo de caixa consolidado via View SQL* | *GMD calculado a partir do histórico de pesagens* | *Distribuição de peso e sexo em tempo real* |

---

## O Problema que Este Projeto Resolve

Produtores rurais dependem de indicadores críticos que sistemas genéricos não calculam bem:

- **GMD (Ganho Médio Diário):** quanto cada animal está ganhando de peso por dia. Calculado cruzando pesagens históricas — operação custosa se feita no Python, leve se feita no banco.
- **Fluxo de Caixa Real:** receitas e despesas unificadas (compra/venda de gado, medicações, vacinações, custos fixos) em uma única visão financeira anual.
- **Gestão de Pastos:** controle de módulos, ocupação por lote, lotação em UA e dias de descanso por módulo.
- **Hereditariedade:** rastreio de reprodução, progenitores e ranking de touros por GMD médio dos filhos.
- **Estoque Virtual:** controle de medicamentos, vacinas e suplementos com alertas de estoque mínimo.

O SGG resolve isso com uma abordagem **Performance-First**: a lógica pesada fica no MySQL via Views otimizadas, e o Python apenas serve o resultado.

---

## Arquitetura

![Arquitetura SGG](photos/SGG-Arch.png)

### Inteligência no Banco de Dados (Views SQL)

Em vez de trazer registros para o Python calcular, o SGG usa **Views otimizadas** — o banco entrega o dado agregado pronto:

| View | Finalidade |
|---|---|
| `v_gmd_analitico` | GMD por animal (CTE + window functions) |
| `v_fluxo_caixa` | Fluxo de caixa anual consolidado |
| `vw_ocupacao_atual` | Módulos com ocupação ativa, UA vs capacidade |
| `vw_dias_descanso` | Módulos livres e dias desde última saída |
| `vw_gmd_por_modulo` | GMD médio dos animais por módulo |
| `vw_gmd_por_touro` | Ranking de touros por GMD médio dos filhos |
| `vw_historico_vaca` | Estatísticas reprodutivas por vaca |
| `vw_saldo_estoque` | Saldo atual por produto com flag de estoque mínimo |

### Repository Pattern

Queries centralizadas em `repositories/` — as rotas nunca escrevem SQL diretamente:

```
repositories/
├── animal_repository.py      # rebanho, progenitores, progênie, reprodução
├── financeiro_repository.py  # fluxo de caixa, agendamentos, custos
├── pasto_repository.py       # pastos, módulos, ocupações, GMD por módulo
├── reproducao_repository.py  # coberturas, partos, ranking de touros
├── estoque_repository.py     # produtos, movimentações, saldo
└── configuracao_repository.py
```

### Escalabilidade

- **Server-Side Pagination:** `LIMIT/OFFSET` no banco — funciona mesmo com milhares de animais.
- **Índices Compostos:** `idx_pesagens_otimizada` e `idx_custos_busca` para buscas e filtros instantâneos.
- **Connection Pooling:** pool de conexões MySQL para evitar overhead de reconexão por request.

### Segurança

- Hash de senha com Werkzeug Security (`generate_password_hash` / `check_password_hash`)
- Proteção de rotas via `@login_required` e validação de `user_id` em todas as queries (multi-tenant)
- Proteção CSRF via Flask-WTF em formulários de mutação
- Rate limiting via Flask-Limiter em rotas sensíveis
- SQL parametrizado em 100% das queries — sem interpolação de strings
- Variáveis sensíveis isoladas em `.env` (nunca commitadas)

---

## Stack

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.10+ |
| Framework Web | Flask 3.x |
| Banco de Dados | MySQL 8.0 |
| Queries | MySQL Connector/Python — SQL puro, sem ORM |
| Frontend | HTML5, CSS3 responsivo, ECharts, Chart.js |
| PDF | Playwright (geração server-side) |
| Autenticação | Flask-Login |
| Segurança | Flask-WTF (CSRF), Flask-Limiter, Werkzeug |
| Testes | Pytest |
| Deploy | Railway (Gunicorn) |

---

## Módulos do Sistema

| Módulo | Funcionalidades |
|---|---|
| **Rebanho** | Cadastro de animais, histórico de pesagens, GMD individual, soft delete, lixeira |
| **Financeiro** | Fluxo de caixa, agendamentos, custos operacionais, vacinações em lote, simulador, relatório PDF |
| **Pastos** | CRUD de pastos/módulos, controle de ocupação, ranking GMD por módulo, dias de descanso |
| **Hereditariedade** | Registro de coberturas e partos, progênie por animal, ranking de touros |
| **Estoque** | Produtos por categoria, movimentações de entrada/saída, alertas de estoque mínimo |
| **Analytics** | Gráficos de distribuição de peso, sexo e GMD do rebanho |
| **Configurações** | Perfil do usuário, centros de custo, metas zootécnicas |

---

## Como Rodar Localmente

### Pré-requisitos

- Python 3.10+
- MySQL Server 8.0 (local ou na nuvem — testado no Aiven)

### 1. Clone o repositório

```bash
git clone https://github.com/Dom1ng0s/sistema_gado.git
cd sistema_gado
```

### 2. Crie e ative o ambiente virtual

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

Para geração de PDF, instale o browser do Playwright:

```bash
playwright install chromium
```

### 4. Configure o ambiente

Crie um arquivo `.env` na raiz baseado no `.env-example`:

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=seu_usuario
DB_PASSWORD=sua_senha
DB_NAME=sistema_gado
SECRET_KEY=chave_secreta_longa

# Email (necessário para recuperação de senha)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=seu@email.com
MAIL_PASSWORD=senha_de_app
MAIL_FROM=SGG Sistema <seu@email.com>
```

### 5. Inicialize o banco de dados

Cria todas as tabelas, Views e índices automaticamente:

```bash
python init_db.py
```

### 6. (Opcional) Popule com dados de demonstração

```bash
python seed_db.py
```

### 7. Execute a aplicação

```bash
python app.py
```

Acesse em: **http://localhost:5000**

---

## Testes

Os testes requerem um banco MySQL local com usuário dedicado:

```sql
CREATE USER 'gado_test'@'localhost' IDENTIFIED BY 'gado123';
GRANT ALL PRIVILEGES ON sistema_gado_test.* TO 'gado_test'@'localhost';
```

O `conftest.py` cria e destrói o banco `sistema_gado_test` automaticamente a cada sessão.

```bash
pytest                                              # todos os testes
pytest tests/test_auth.py                           # módulo específico
pytest tests/test_auth.py::test_login_sucesso       # teste único
```

---

## Deploy (Railway)

O projeto está publicado em **[sistemadogado.up.railway.app](https://sistemadogado.up.railway.app/)** via [Railway](https://railway.app/).

### Configuração do deploy

O servidor de produção usa Gunicorn (definido em `Procfile` e `railway.toml`):

```
web: gunicorn app:app
```

### Variáveis de ambiente no Railway

Configure as seguintes variáveis no painel do Railway (mesmas do `.env-example`):

| Variável | Descrição |
|---|---|
| `DB_HOST` | Host do MySQL (ex: instância Aiven ou Railway MySQL) |
| `DB_PORT` | Porta (padrão: 3306) |
| `DB_USER` | Usuário do banco |
| `DB_PASSWORD` | Senha do banco |
| `DB_NAME` | Nome do banco de dados |
| `SECRET_KEY` | Chave secreta Flask — gere com `python -c "import secrets; print(secrets.token_hex(32))"` |
| `MAIL_SERVER` | Servidor SMTP (ex: `smtp.gmail.com`) |
| `MAIL_PORT` | Porta SMTP (ex: `587`) |
| `MAIL_USERNAME` | Email SMTP |
| `MAIL_PASSWORD` | Senha de app Gmail (não a senha da conta) |
| `MAIL_FROM` | Remetente exibido nos emails |

### Banco de dados em produção

Após o primeiro deploy, execute o script de inicialização do banco uma única vez via Railway CLI ou console:

```bash
python init_db.py
```

---

## Estrutura do Projeto

```
sistema_gado/
├── app.py                    # Factory e registro de blueprints
├── db_config.py              # Pool de conexões MySQL
├── extensions.py             # Rate limiter
├── init_db.py                # DDL: tabelas, views, índices
├── seed_db.py                # Dados de demonstração
├── models.py                 # User model (Flask-Login)
├── routes/                   # Blueprints por domínio
│   ├── auth.py
│   ├── operacional.py        # Rebanho, pesagens, hereditariedade
│   ├── financeiro.py
│   ├── pastos.py
│   ├── estoque.py
│   ├── configuracoes.py
│   ├── api.py                # Endpoints JSON
│   └── validators.py
├── repositories/             # Toda query SQL fica aqui
├── utils/
│   └── email_service.py      # Envio de código de recuperação de senha
├── templates/                # Jinja2
├── static/
│   ├── css/design_system.css
│   └── components.html
└── tests/
```

---

## Autor

**Davi Domingos de Oliveira**  
Estudante de Ciência da Computação — UFAL | Backend Developer
