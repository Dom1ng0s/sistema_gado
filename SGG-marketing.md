# SGG — Sistema de Gestão de Gado
## Documento de Produto e Posicionamento

*Versão 1.0 — Junho 2026*

---

## O que é o SGG

ERP zootécnico para pecuária de corte que substitui planilha e caderno por painel de controle com rastreamento individual de animais, cálculo automático de GMD, fluxo de caixa integrado e cotações do boi gordo em tempo real.

O sistema está em produção em [sistemadogado.up.railway.app](https://sistemadogado.up.railway.app), com dataset real de 235 animais de referência. Acesso: `demonstracao` / `demonstracao`.

---

## O problema que resolve

Gado de corte é um ativo de R$ 1.800 a R$ 2.000 por cabeça. Um rebanho de 235 animais representa R$ 433 mil em campo. Até hoje, a maioria dos produtores de médio porte toma decisões de compra e venda sem saber o GMD real de cada brinco.

O ciclo atual do pecuarista sem sistema:

1. Pesa o lote na balança de curral
2. Anota no caderno ou planilha
3. Calcula a média do lote manualmente — quando calcula
4. Descobre que um animal estava ruim **na hora de vender**, depois de meses consumindo pasto e suplemento sem retorno

O SGG inverte esse ciclo: o produtor entra no painel e vê imediatamente quais animais estão abaixo do GMD mínimo, identificados pelo brinco, antes que virem prejuízo.

---

## Funcionalidades do sistema atual

### Gestão do Rebanho
- Cadastro individual por brinco com raça, sexo, data de nascimento e data de compra
- Pesagem em lote — 100 animais registrados em uma única operação
- Importação e exportação CSV — compatível com planilhas existentes
- Relatório PDF gerado server-side via Playwright
- Soft delete com lixeira restaurável

### GMD (Ganho Médio Diário)
- Calculado automaticamente via view SQL com `LAG()` e CTE — sem processamento no Python
- Alerta visual de animais abaixo do limiar configurado
- Ranking de módulos de pasto por GMD produzido

### Dashboard Financeiro
- Valor do rebanho ativo em tempo real
- Custo real da arroba produzida (últimos 90 dias)
- Custo diário por cabeça
- Fluxo de caixa anual consolidado (compras, vendas, medicações, custos operacionais)
- P&L por lote — margem bruta de cada lote desde a compra até as vendas parciais
- Simulador de ponto de equilíbrio com parâmetros sugeridos a partir dos dados reais do sistema
- Contas a pagar com alertas de vencimento

### Calendário Sanitário
- Protocolos vacinais recorrentes com intervalo configurável
- Alertas por e-mail 7 dias antes do vencimento — sem precisar abrir o sistema
- Vacinação em lote com um único submit

### Gestão de Pastos
- Módulos de pastejo rotacionado com capacidade em UA
- Ocupação atual vs. capacidade máxima (alerta de superlotação)
- Dias de descanso por módulo desde a última saída

### Hereditariedade e Reprodução
- Registro de cobertura com touro do rebanho ou externo (sêmen)
- Diagnóstico de prenhez com data prevista de parto (cobertura + 285 dias)
- Geração automática do bezerro ao registrar parto com resultado "vivo"
- Ranking de touros por GMD médio dos filhos
- Histórico reprodutivo por vaca (partos, taxa de sucesso)

### Estoque Virtual
- Controle de medicamentos, vacinas, suplementos e minerais por unidade
- Saldo atual com flag de estoque mínimo atingido
- Alerta por e-mail semanal de produtos críticos
- Rastreamento de validade por lote de fabricante

### Cotações
- Scraper próprio de 33 praças brasileiras (boi gordo e novilha)
- Cotação do dia disponível no próprio painel do rebanho
- Modal com mapa nacional de preços por região

---

## Diferenciais técnicos

**SQL como motor de cálculo.** O GMD de cada animal é calculado via `v_gmd_analitico` — uma view com CTE e window functions `LAG()`. A rota Flask recebe o dado pronto, sem iterar sobre pesagens no Python. Isso significa velocidade em rebanhos com anos de histórico e lógica auditável diretamente no banco.

**Multi-tenant com isolamento verificado em teste.** Cada fazenda vê apenas seus dados. O isolamento é testado automaticamente em nível HTTP — o `test_tenant_isolation.py` verifica que um usuário não consegue visualizar, vender, pesar, medicar ou excluir animais de outro usuário via requisição direta.

**Alertas proativos sem broker externo.** APScheduler roda dentro do processo Flask e dispara e-mails às 8h: contas vencendo em 3 dias, protocolos sanitários em 7 dias, estoque crítico às segundas. Sem Redis, sem Celery, sem fila.

**Vocabulário pecuarista.** A interface fala brinco, lote, arroba, UA, prenhez, desmama — não "tag", "inventory", "unit". Campos, filtros e relatórios usam a terminologia que o produtor e o zootecnista já conhecem.

---

## Métricas do dataset de referência (Fazenda São Marcos — demo interno)

| Indicador | Valor |
|-----------|-------|
| Animais no rebanho | 235 (193 machos / 42 fêmeas) |
| GMD médio do rebanho | 0,730 kg/dia |
| Animais abaixo do GMD mínimo | 17 (< 0,395 kg/dia) |
| Valor do rebanho ativo | R$ 433.640,87 |
| Custo de produção | R$ 102,52/@ |
| Custo diário por cabeça | R$ 2,50/cab |
| Praças monitoradas | 33 |

> **Atenção:** A Fazenda São Marcos é um caso de teste interno. Esses números são dados reais usados para validar o sistema — não há produtor-cliente por trás deles.

---

## Stack

| Tecnologia | Papel |
|-----------|-------|
| Flask 3.x | Servidor web, blueprints por domínio |
| MySQL 8.0 | Banco principal — window functions para GMD |
| Playwright | Geração de PDF server-side |
| APScheduler | Jobs de alerta (sem broker externo) |
| Railway | Deploy com MySQL gerenciado |
| Flask-Limiter | Rate limiting nas rotas de API e login |

SQL puro — sem ORM. A decisão é intencional: as views que calculam GMD e fluxo de caixa usam CTEs e window functions que não têm equivalente direto em SQLAlchemy sem perder legibilidade.

---

## Lacunas atuais

Esta seção documenta o que falta antes de o produto estar pronto para aquisição em escala. Sem ilusão sobre o estado atual.

### 1. Sem landing page pública

A rota `/` redireciona direto para o login. O produtor que chega pela primeira vez não vê o que o sistema faz, não tem razão para criar conta e não encontra nem o botão de cadastro.

A rota `/novo_usuario` existe e é pública — mas nenhuma página linka para ela.

**Impacto:** freemium não funciona sem landing page. Qualquer aquisição hoje depende de contato direto do fundador.

---

### 2. Sem onboarding após o cadastro

Novo usuário cria conta, faz login e cai no painel vazio. Zero animais, zero instrução, zero contexto. Não há wizard de setup, sugestão de primeiro passo ou dado de exemplo.

**Impacto:** taxa de abandono alta na primeira sessão. Produtores com perfil menos técnico abandonam antes de cadastrar o primeiro animal.

---

### 3. Sem analytics

Nenhum dado de tráfego, cadastros, funcionalidades mais usadas ou ponto de abandono. Não é possível saber se alguém está acessando o demo, onde para e o que testa.

**Impacto:** impossível priorizar melhorias com base em comportamento real. Todas as decisões de produto são baseadas em intuição do fundador.

---

### 4. Sem usuários pagantes

O sistema não tem clientes reais ainda. A Fazenda São Marcos é um caso de teste interno. Não há depoimentos, não há feedback de uso contínuo e não há receita.

**Impacto:** as hipóteses de produto (quais features importam, qual dor é mais crítica) ainda não foram validadas por ninguém além do desenvolvedor.

---

### 5. Competidores desconhecidos

Não foi feito mapeamento de mercado com produtores reais. Os concorrentes listados internamente (FazFácil, Sysagri, AgroManager) são hipóteses — nenhum produtor foi entrevistado sobre o que usa hoje.

**Impacto:** posicionamento e diferenciação construídos sem saber contra quem competem de fato. Pode estar resolvendo um problema que o produtor já resolveu com outra ferramenta.

---

### 6. Modelo de negócio indefinido

Freemium nos primeiros 3 meses está decidido como estratégia de entrada. O que vem depois — preço, limite de features no plano gratuito, critério de conversão — ainda não foi definido.

**Impacto:** sem modelo de negócio, o período freemium é aquisição de usuários sem objetivo de conversão. Os primeiros 3 meses precisam ser instrumentalizados para coletar os dados que vão informar o pricing.

---

## Próximos passos recomendados

Ordenados por impacto no desbloqueio do modelo freemium:

1. **Landing page** — página pública em `/` com headline, 3 features, métricas reais do demo e CTA "Criar conta grátis" linkando para `/novo_usuario`
2. **Analytics** — Plausible ou Google Analytics na landing e no painel interno
3. **Entrevistar 5 produtores** — pergunta única: "como você controla o rebanho hoje?" A resposta substitui as hipóteses de concorrente e valida (ou invalida) o posicionamento
4. **Onboarding mínimo** — checklist de 3 passos na primeira sessão: nome da fazenda → importar CSV ou cadastrar primeiro animal → primeira pesagem
5. **Pricing** — definir o que fica no plano grátis e o que converte para pago, baseado nos dados de uso dos primeiros 30 dias de freemium

---

*Documento interno — não é material de campanha. Algumas seções contêm hipóteses não validadas sinalizadas explicitamente.*
