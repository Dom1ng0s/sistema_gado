
# 🐮 Sistema de Gestão de Gado (GMD & Financeiro)

Sistema web de alta performance para gestão pecuária, focado em controle zootécnico (GMD) e análise financeira rigorosa. Desenvolvido com Python (Flask) e MySQL, utilizando arquitetura otimizada com Views SQL para processamento de dados.

## 🚀 Funcionalidades Implementadas

### 1. Gestão de Rebanho
* **Cadastro Completo:** Registro de animais com Brinco, Sexo, Data de Compra e Peso Inicial.
* **Painel Otimizado:** Listagem ultrarrápida com **Paginação Server-Side** (10 itens/página) e Busca por Brinco.
* **Status Inteligente:** Classificação automática (Ativo/Vendido) baseada na data de saída real.

### 2. Inteligência Zootécnica
* **Cálculo de GMD:** O sistema calcula automaticamente o *Ganho Médio Diário* (kg/dia) de cada animal com base no histórico de pesagens (via View SQL).
* **Ficha Técnica:** Exibição detalhada de evolução de peso e histórico sanitário (vacinas e medicamentos).

### 3. Controle Financeiro (Fluxo de Caixa)
* **Dashboard Otimizado:** Relatório instantâneo alimentado por Views SQL (Complexidade O(1)).
* **Custos Operacionais:** Módulo para lançamento de despesas fixas (Salários, Arrendamento) e variáveis (Manutenção, Gasolina).
* **Balanço Anual:** Visão consolidada de Entradas vs. Saídas (Compras + Medicação + Custos).

---

## 🛠️ Instalação e Configuração

### Pré-requisitos
* Python 3.10+
* MySQL 8.0+ (Local ou Nuvem)

### Passo 1: Preparar o Ambiente
```bash
# Criar ambiente virtual
python -m venv venv

# Ativar (Windows)
venv\Scripts\activate
# Ativar (Linux/Mac)
source venv/bin/activate
````

### Passo 2: Instalar Dependências

```bash
pip install -r requirements.txt
```

### Passo 3: Configurar Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto com suas credenciais do banco:

```ini
DB_HOST=seu-host-mysql
DB_USER=seu-usuario
DB_PASSWORD=sua-senha
DB_NAME=defaultdb
DB_PORT=3306
SECRET_KEY=sua_chave_secreta_segura
```

### Passo 4: Inicializar o Banco de Dados

Execute o script mestre que cria as Tabelas e as Views de Inteligência:

```bash
python init_db.py
```

*Isso criará automaticamente o usuário admin padrão se não existir:*

  * **Usuário:** `admin`
  * **Senha:** `admin123`

### Passo 5: Rodar a Aplicação

```bash
python app.py
```

Acesse em: `http://localhost:5000`

-----

## 🏗️ Arquitetura Técnica

O projeto segue princípios de **Performance First**:

1.  **Views SQL (`v_fluxo_caixa`, `v_gmd_analitico`):**

      * Toda a lógica matemática (somas, médias, datas) reside no banco de dados.
      * O Python atua apenas como interface, garantindo resposta em milissegundos.

2.  **Server-Side Pagination:**

      * O Painel busca apenas a "fatia" necessária de dados (LIMIT/OFFSET), economizando memória e permitindo escalar para milhares de animais.

3.  **Segurança Implementada:**

      * Hash de Senhas robusto (Werkzeug Security).
      * Gerenciamento de Sessão seguro (Flask-Login).
      * Proteção de Rotas (`@login_required`).



