<div align="center">

# 🐮 Sistema de Gestão de Gado (SGG)

**ERP Zootécnico de alta performance para o agronegócio**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-Framework-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?style=for-the-badge&logo=mysql&logoColor=white)](https://mysql.com)
[![Status](https://img.shields.io/badge/Status-Em%20Desenvolvimento-yellow?style=for-the-badge)](https://github.com/Dom1ng0s/sistema_gado)

> Solução web para pecuaristas que precisam controlar rebanho, calcular **GMD (Ganho Médio Diário)** e acompanhar o **fluxo de caixa** da fazenda — tudo em um só lugar, com lógica de cálculo delegada ao banco de dados para máxima performance.

</div>

---

## 📸 Capturas de Tela

| Dashboard Financeiro | Análise Zootécnica (GMD) | Analytics do Rebanho |
|:---:|:---:|:---:|
| ![Financeiro](photos/financeiro.png) | ![Animal](photos/animal.png) | ![Rebanho](photos/rebanho.png) |
| *Fluxo de caixa consolidado via View SQL* | *GMD calculado a partir do histórico de pesagens* | *Distribuição de peso e sexo em tempo real* |

---

## 💡 O Problema que Este Projeto Resolve

Produtores rurais dependem de dois indicadores críticos que sistemas genéricos não calculam bem:

- **GMD (Ganho Médio Diário):** quanto cada animal está ganhando de peso por dia. Calculado cruzando a primeira e a última pesagem do histórico — operação custosa se feita no Python, leve se feita no banco.
- **Fluxo de Caixa Real:** receitas e despesas da fazenda unificadas (compra/venda de gado, medicações, custos fixos) em uma única visão financeira anual.

O SGG resolve isso com uma abordagem **Performance-First**: a lógica pesada fica no MySQL, e o Python apenas serve o resultado.

---

## 🏗️ Arquitetura e Decisões Técnicas

### 🧠 Inteligência no Banco de Dados (Views SQL)

Em vez de trazer todos os registros para o Python calcular, o SGG usa **Views otimizadas** — o banco entrega o dado agregado pronto, com custo O(1) para a aplicação:

```sql
-- v_gmd_analitico: Calcula GMD cruzando primeira e última pesagem
-- Resultado: dias em cocho, ganho total (kg) e GMD por animal

-- v_fluxo_caixa: Unifica 4 tabelas (Vendas, Compras, Medicações, Custos Fixos)
-- Resultado: visão financeira anual sem nenhuma agregação no Python
```

### ⚡ Escalabilidade sem Travar o Navegador

- **Server-Side Pagination:** o painel principal usa `LIMIT/OFFSET` no banco — funciona mesmo com milhares de animais cadastrados.
- **Índices Compostos:** `idx_pesagens_otimizada` e `idx_custos_busca` garantem buscas e filtros instantâneos à medida que o rebanho cresce.
- **Connection Pooling:** uso do `mysql-connector-python` com pool de conexões para evitar overhead de reconexão a cada request.

### 🛡️ Segurança e Boas Práticas

- **Arquitetura MVC** com separação clara entre Rotas (`/routes`), Templates (`/templates`) e camada de dados (`models.py`, `db_config.py`).
- **Hash de senha** com `Werkzeug Security` (`generate_password_hash` / `check_password_hash`).
- **Proteção de rotas** via `@login_required` e validação de propriedade dos dados (multi-tenant ready).
- **Variáveis sensíveis** isoladas em `.env` (nunca commitadas).
- **Testes automatizados** com `pytest` e `conftest.py` para fixtures de banco.

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| **Linguagem** | Python 3.10+ |
| **Framework Web** | Flask |
| **Banco de Dados** | MySQL 8.0 |
| **ORM / Queries** | MySQL Connector/Python (SQL puro + Views) |
| **Frontend** | HTML5, CSS3 responsivo, Chart.js |
| **Testes** | Pytest |
| **Segurança** | Werkzeug Security |
| **Config** | python-dotenv |

---

## ⚙️ Como Rodar Localmente

### Pré-requisitos

- Python 3.10+
- MySQL Server (local ou na nuvem — testado no Aiven)

### 1. Clone o repositório

```bash
git clone https://github.com/Dom1ng0s/sistema_gado.git
cd sistema_gado
```

### 2. Crie e ative o ambiente virtual

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure o ambiente

Crie um arquivo `.env` na raiz do projeto baseado no `.env-example`:

```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=sua_senha
DB_NAME=sistema_gado
DB_PORT=3306
SECRET_KEY=uma_chave_secreta_forte
```

### 5. Inicialize o banco de dados

Este script cria todas as tabelas, Views e índices automaticamente:

```bash
python init_db.py
```

### 6. (Opcional) Popule com dados de demonstração

Para ver o dashboard com dados realistas:

```bash
python seed_db.py
```

### 7. Execute a aplicação

```bash
python app.py
```

Acesse em: **http://localhost:5000**

---

## 🧪 Executando os Testes

```bash
pytest tests/
```

---

## 📁 Estrutura do Projeto

```
sistema_gado/
├── app.py              # Ponto de entrada da aplicação Flask
├── db_config.py        # Configuração e pool de conexões MySQL
├── models.py           # Queries e lógica de acesso ao banco
├── init_db.py          # Script de criação de tabelas, Views e índices
├── seed_db.py          # Dados de demonstração realistas
├── conftest.py         # Fixtures de teste (pytest)
├── routes/             # Blueprints Flask por módulo (financeiro, animal, rebanho...)
├── templates/          # Templates HTML (Jinja2)
├── static/             # CSS, JS e assets
├── tests/              # Testes automatizados
├── photos/             # Screenshots do sistema
└── .env-example        # Modelo de configuração de ambiente
```

---

## 🗺️ Próximas Funcionalidades

- [ ] API REST para integração com aplicativo mobile
- [ ] Exportação de relatórios em PDF
- [ ] Deploy com Docker + CI/CD via GitHub Actions
- [ ] Dashboard de alertas (animais abaixo do GMD esperado)

---

## 👤 Autor

**Davi Domingos de Oliveira**
Estudante de Ciência da Computação — UFAL | Backend Developer

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=flat&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/davidomingosdeoliveira/)
[![GitHub](https://img.shields.io/badge/GitHub-181717?style=flat&logo=github&logoColor=white)](https://github.com/Dom1ng0s)
[![Email](https://img.shields.io/badge/Email-D14836?style=flat&logo=gmail&logoColor=white)](mailto:odomingosdavi@gmail.com)
