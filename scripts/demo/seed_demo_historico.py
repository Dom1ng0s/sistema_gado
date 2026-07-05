#!/usr/bin/env python3
"""
Seed histórico: conta demonstracao — simulação econômica completa 2020-01-01 a 2026-06-30.

Reescrita completa (v2) do seed original. Reconstrói do zero os dados de gestão vinculados
ao usuário 'demonstracao' (NUNCA altera usuarios/configuracoes). Usa mysql.connector puro —
este projeto não usa SQLAlchemy/ORM (ver CLAUDE.md: "SQL puro — não introduzir SQLAlchemy
ou ORM"), então app.app_context()/db.session não se aplicam aqui.

Modelo de crescimento (unificado para todo animal individualmente rastreado — lote comercial
ou cria nascida na fazenda):
  - Cada animal recebe, na criação, uma classe de GMD sorteada: 90% normal (~0.87kg/dia,
    N(0.87,0.06) truncada [0.70,1.05]), 5% "ruim" (0.20-0.40) e 5% "excepcional" (1.30-1.60).
  - O destino (venda ou óbito) é resolvido UMA VEZ, no momento em que a janela de vida do
    animal é conhecida: para lotes comerciais isso é quando o lote chega à frente da fila de
    venda (a cadência de venda é uma decisão de negócio, não depende do peso individual);
    para crias é a própria data em que a trajetória individual atinge o peso-alvo de venda.
    A probabilidade de morte usa a taxa anual composta sobre os dias efetivamente vividos
    nessa janela — se "morre", morre em uma data aleatória dentro da janela; senão, sobrevive
    até o fim dela. Isso substitui varreduras de mortalidade separadas e garante que um animal
    morto pare de gerar eventos (reprodução, medicação, pesagem) depois do óbito.
  - O peso em cada ponto no tempo é sempre peso_inicial + gmd*dias — nunca um valor
    independente sorteado à parte — garantindo coerência cronológica pesagem a pesagem.

Outras decisões de modelagem:
  - Aporte de capital = custos_operacionais com valor NEGATIVO (categoria='Aporte'); é o único
    jeito de representar uma entrada de caixa avulsa neste schema (receita só existe nativamente
    via animais.preco_venda). Soma corretamente em v_fluxo_caixa. financeiro.html já sabe
    renderizar valor<0 como crédito (verde).
  - Mortalidade: sem coluna de status em `animais`. Modelada como data_venda=data_óbito,
    preco_venda=0.00 (sai de "ativos", não gera receita) + 1 linha de custos_operacionais
    (valor=0, categoria='Perda') para rastreabilidade da causa.
  - Compra de insumos (estaca/arame/sal) agora também gera lançamento em custos_operacionais
    (categoria/tipo iguais aos de cost_centers: 'Fixo'/'Manutenção' e 'Variavel'/'Nutrição'),
    não só em estoque_movimentacoes — sem isso a compra fica invisível na página Financeiro
    (v_fluxo_caixa só olha custos_operacionais/medicacoes/animais, nunca estoque).
  - Sexagem: lotes comerciais (reposição comprada) saem 80% M / 20% F — essa é a maior massa
    do rebanho ao longo do tempo, então é ela que domina a proporção geral pedida (80/20).
    Crias nascidas na fazenda mantêm 50/50 biológico; fêmeas nascidas têm 55% de chance de
    virar matriz (retida, sem trajetória de venda) — as demais são vendidas como as demais.
  - Diagnóstico de prenhez (Fase 5.3): todo registro de reprodução já tem resultado conhecido
    (o schema exige `resultado` NOT NULL sem opção "pendente" — replicando o comportamento real
    da rota routes/operacional.py:registrar_reproducao, que sempre grava um resultado definitivo).
    Para as coberturas mais recentes, cuja data_parto prevista (cobertura + 285 dias) só ocorre
    depois de 30/06/2026, gravamos resultado='vivo' com data_parto=NULL (a rota permite essa
    combinação) e diagnostico='positivo' — isso é o que vw_partos_previstos exige para aparecer
    no widget "partos previstos", e é a única forma válida, dentro do schema atual, de simular
    uma gestação ainda em curso na data de hoje.

Rodar:
    python scripts/seed_demo_historico.py
"""
import os
import random
import heapq
from datetime import date, timedelta
from dotenv import load_dotenv
import mysql.connector

load_dotenv()
random.seed(20260630)

# ══════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════
START = date(2020, 1, 1)
END = date(2026, 6, 30)
ARROBA_KG = 30
LOTE_SIZE = 20
TARGET_WIP = 12  # lotes simultaneamente em curral no regime estável maduro
FOUNDER_GMD_ALVO = 0.80  # GMD usado só para calcular a duração da carência (regra do enunciado)

SALARIO_MINIMO = {2020: 1045, 2021: 1100, 2022: 1212, 2023: 1320, 2024: 1412, 2025: 1518, 2026: 1518}
VAQUEIRO_SALARIO = 2200.00

# preço da arroba: venda sorteada em torno de um centro anual, compra = venda + ágio(5-30)
VENDA_CENTRO_ANO = {2020: 278, 2021: 294, 2022: 308, 2023: 296, 2024: 315, 2025: 330, 2026: 340}

RACAS = ['Nelore'] * 8 + ['Angus', 'Brahman', 'Girolando']
MORTE_CAUSAS = ['Raio', 'Doença respiratória', 'Picada de cobra', 'Complicação no parto',
                'Afogamento', 'Acidente em cerca']

conn = mysql.connector.connect(
    host=os.getenv('DB_HOST'), user=os.getenv('DB_USER'), password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME'), port=int(os.getenv('DB_PORT', 3306)), autocommit=False,
)
cur = conn.cursor()

caixa_ledger = []  # (data, valor_assinado, categoria) — para validação/relatório, não vai ao banco
pesagens_rows = []
medicacoes_rows = []
custos_rows = []
reproducao_rows = []
estoque_mov_rows = []


def registrar_caixa(d, valor, categoria):
    caixa_ledger.append((d, valor, categoria))


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def rdate(s, e):
    if e <= s:
        return s
    return s + timedelta(days=random.randint(0, (e - s).days))


def raca():
    return random.choice(RACAS)


def preco_arroba(d):
    """(compra, venda) do dia — venda em torno do centro anual, compra = venda + ágio(5-30),
    sempre dentro de [270,380] e respeitando compra > venda."""
    centro = VENDA_CENTRO_ANO.get(d.year, 300)
    venda = clamp(round(random.gauss(centro, 12), 2), 270.0, 350.0)
    agio = round(random.uniform(5, 30), 2)
    compra = min(380.0, round(venda + agio, 2))
    return compra, venda


def sorteia_gmd():
    """90% normal, 5% ruim, 5% excepcional — usado para TODO animal com trajetória de peso."""
    r = random.random()
    if r < 0.05:
        return round(random.uniform(0.20, 0.40), 3)
    if r < 0.10:
        return round(random.uniform(1.30, 1.60), 3)
    return round(clamp(random.gauss(0.87, 0.06), 0.70, 1.05), 3)


def resolve_destino(entrada, saida_planejada, taxa_anual=0.02):
    """Resolve, de uma vez, se o animal morre antes de `saida_planejada` (ou antes de END, se
    `saida_planejada` for None) ou se sobrevive até lá. Usa taxa composta sobre os dias vividos."""
    limite = saida_planejada or END
    if entrada >= limite:
        return ('sobrevive', saida_planejada)
    dias = (limite - entrada).days
    prob_morte = 1 - (1 - taxa_anual) ** (dias / 365.25)
    if random.random() < prob_morte:
        return ('morte', rdate(entrada, limite))
    return ('sobrevive', saida_planejada)


def registra_crescimento(aid, peso0, data0, gmd, data_fim, passo=90, peso_max=780.0):
    """Gera pesagens cronologicamente coerentes (peso = peso0 + gmd*dias) do início até
    data_fim (inclusive), a cada `passo` dias, saturando em peso_max (ex: peso de abate para
    animais de engorda, peso de vaca adulta para matrizes retidas). Retorna o peso final."""
    pesagens_rows.append((aid, data0, round(peso0, 2)))
    if data_fim <= data0:
        return round(peso0, 2)
    dias_totais = (data_fim - data0).days
    t = passo
    while t < dias_totais:
        peso_t = round(clamp(peso0 + gmd * t, peso0, peso_max), 2)
        pesagens_rows.append((aid, data0 + timedelta(days=t), peso_t))
        t += passo
    peso_final = round(clamp(peso0 + gmd * dias_totais, peso0, peso_max), 2)
    pesagens_rows.append((aid, data_fim, peso_final))
    return peso_final


def bulk(sql, rows, chunk=500):
    if not rows:
        return
    for i in range(0, len(rows), chunk):
        cur.executemany(sql, rows[i:i + chunk])
    conn.commit()


def lanca_insumo_financeiro(categoria, tipo_custo, valor, data, descricao):
    custos_rows.append((uid, categoria, tipo_custo, round(valor, 2), data, descricao))
    registrar_caixa(data, -valor, 'estoque')


def mov(pid, tipo, qtd, custo_unit, data, motivo, categoria_fin=None, tipo_custo_fin=None):
    estoque_mov_rows.append((uid, pid, tipo, qtd, custo_unit, motivo, data))
    if tipo == 'entrada' and custo_unit:
        valor_total = round(qtd * custo_unit, 2)
        if categoria_fin:
            lanca_insumo_financeiro(categoria_fin, tipo_custo_fin, valor_total, data, motivo)


try:
    # ══════════════════════════════════════════════════════════════
    # [0/13] USUÁRIO — localizar (NÃO alterar usuarios/configuracoes)
    # ══════════════════════════════════════════════════════════════
    print("[0/13] Localizando usuário 'demonstracao'...")
    cur.execute("SELECT id FROM usuarios WHERE LOWER(username) = LOWER(%s)", ('demonstracao',))
    row = cur.fetchone()
    if not row:
        raise SystemExit("Usuário 'demonstracao' não encontrado. Crie a conta antes de rodar este seed.")
    uid = row[0]
    print(f"      uid={uid}")

    # ══════════════════════════════════════════════════════════════
    # [1/13] LIMPEZA — apaga dados de gestão vinculados ao user_id
    # ══════════════════════════════════════════════════════════════
    print("[1/13] Limpando dados de gestão anteriores...")
    cur.execute("SELECT id FROM animais WHERE user_id = %s", (uid,))
    old_aids = [r[0] for r in cur.fetchall()]
    if old_aids:
        ph = ','.join(['%s'] * len(old_aids))
        cur.execute(f"DELETE FROM reproducao WHERE vaca_id IN ({ph})", old_aids)
        cur.execute(f"DELETE FROM pesagens WHERE animal_id IN ({ph})", old_aids)
        cur.execute(f"DELETE FROM medicacoes WHERE animal_id IN ({ph})", old_aids)
    cur.execute("SELECT id FROM modulos WHERE user_id = %s", (uid,))
    old_mids = [r[0] for r in cur.fetchall()]
    if old_mids:
        pm = ','.join(['%s'] * len(old_mids))
        cur.execute(f"SELECT id FROM ocupacoes WHERE modulo_id IN ({pm})", old_mids)
        old_oids = [r[0] for r in cur.fetchall()]
        if old_oids:
            po = ','.join(['%s'] * len(old_oids))
            cur.execute(f"DELETE FROM ocupacao_animais WHERE ocupacao_id IN ({po})", old_oids)
            cur.execute(f"DELETE FROM ocupacoes WHERE id IN ({po})", old_oids)
        cur.execute(f"DELETE FROM modulos WHERE id IN ({pm})", old_mids)
    cur.execute("DELETE FROM pastos WHERE user_id = %s", (uid,))
    if old_aids:
        cur.execute(f"UPDATE animais SET pai_id = NULL, mae_id = NULL WHERE id IN ({ph})", old_aids)
        cur.execute(f"DELETE FROM animais WHERE id IN ({ph})", old_aids)
    cur.execute("DELETE FROM custos_operacionais WHERE user_id = %s", (uid,))
    cur.execute("DELETE FROM financial_schedule WHERE user_id = %s", (uid,))
    cur.execute("SELECT id FROM estoque_produtos WHERE user_id = %s", (uid,))
    old_pids = [r[0] for r in cur.fetchall()]
    if old_pids:
        pp = ','.join(['%s'] * len(old_pids))
        cur.execute(f"DELETE FROM estoque_movimentacoes WHERE produto_id IN ({pp})", old_pids)
    cur.execute("DELETE FROM estoque_produtos WHERE user_id = %s", (uid,))
    cur.execute("SELECT id FROM lotes WHERE user_id = %s", (uid,))
    old_lids = [r[0] for r in cur.fetchall()]
    if old_lids:
        pl = ','.join(['%s'] * len(old_lids))
        cur.execute(f"DELETE FROM lotes WHERE id IN ({pl})", old_lids)
    conn.commit()
    print(f"      {len(old_aids)} animais antigos removidos")

    # ══════════════════════════════════════════════════════════════
    # [2/13] APORTE DE CAPITAL INICIAL
    # ══════════════════════════════════════════════════════════════
    print("[2/13] Lançando aporte de capital inicial (R$ 600.000,00)...")
    custos_rows.append((uid, 'Aporte', 'Capital Inicial', -600000.00, START,
                         'Aporte de Capital Inicial - Sócios (financia o Vale da Morte do 1º ciclo)'))
    registrar_caixa(START, 600000.00, 'aporte')

    # ══════════════════════════════════════════════════════════════
    # [3/13] PASTOS
    # ══════════════════════════════════════════════════════════════
    print("[3/13] Criando pastos...")
    pasto_config = [
        ('Piquete Norte A', 'Brachiaria Brizantha', 35.0, 55),
        ('Piquete Norte B', 'Brachiaria Brizantha', 35.0, 55),
        ('Piquete Sul A', 'Mombaça', 30.0, 50),
        ('Piquete Sul B', 'Mombaça', 30.0, 50),
        ('Piquete Centro', 'Panicum Maximum', 28.0, 45),
        ('Pasto Matrizes', 'Brachiaria Ruziziensis', 22.0, 35),
        ('Pasto Recria', 'Brachiaria Decumbens', 18.0, 35),
    ]
    modulos = []
    for nome, forr, area, cap in pasto_config:
        cur.execute(
            "INSERT INTO pastos (user_id, nome, area_hectares, forrageira, capacidade_ua) "
            "VALUES (%s, %s, %s, %s, %s)", (uid, nome, area, forr, cap)
        )
        pasto_id = cur.lastrowid
        cur.execute(
            "INSERT INTO modulos (pasto_id, user_id, nome, area_hectares, capacidade_ua) "
            "VALUES (%s, %s, %s, %s, %s)", (pasto_id, uid, f"Módulo {nome}", area, cap)
        )
        modulos.append(cur.lastrowid)
    conn.commit()
    print(f"      {len(modulos)} módulos criados")

    # ══════════════════════════════════════════════════════════════
    # [4/13] ESTOQUE — produtos + saldo inicial (Jan/2020) + cadência
    # ══════════════════════════════════════════════════════════════
    print("[4/13] Criando produtos de estoque e programando movimentações...")

    def criar_produto(nome, unidade, categoria, minimo):
        cur.execute(
            "INSERT INTO estoque_produtos (user_id, nome, unidade, categoria, estoque_minimo) "
            "VALUES (%s, %s, %s, %s, %s)", (uid, nome, unidade, categoria, minimo)
        )
        return cur.lastrowid

    p_estaca = criar_produto('Estaca de Madeira', 'unidade', 'outro', 80)
    p_arame = criar_produto('Arame Farpado (rolo 250m)', 'rolo', 'outro', 2)
    p_sal = criar_produto('Sal Mineral / Proteinado (saco 30kg)', 'saco', 'mineral', 30)
    p_aftosa = criar_produto('Vacina Febre Aftosa', 'dose', 'vacina', 50)
    p_anab = criar_produto('Anabólico Bovino', 'dose', 'medicamento', 30)
    conn.commit()

    # saldo inicial
    mov(p_estaca, 'entrada', 100, 1.00, START, 'Saldo inicial', 'Fixo', 'Manutenção')
    mov(p_arame, 'entrada', 2, 300.00, START, 'Saldo inicial', 'Fixo', 'Manutenção')
    mov(p_sal, 'entrada', 20, 100.00, START, 'Saldo inicial', 'Variavel', 'Nutrição')

    # consumo mensal: 500 estacas/ano, 10 arames/ano, 200 sacos de sal/ano — + reposição periódica
    d = date(START.year, START.month, 15)
    while d <= END:
        estacas_qtd = 500 // 12 + (1 if d.month <= 500 % 12 else 0)
        sal_qtd = 200 // 12 + (1 if d.month <= 200 % 12 else 0)
        mov(p_estaca, 'saida', estacas_qtd, None, d, 'Consumo mensal de manutenção de cercas')
        mov(p_sal, 'saida', sal_qtd, None, d, 'Consumo mensal do rebanho (nutrição)')
        if d.month in (2, 5, 8, 11):
            mov(p_arame, 'saida', random.randint(2, 3), None, d, 'Reforma de cercas')
        if d.month in (3, 9):
            mov(p_estaca, 'entrada', 250, round(random.uniform(0.95, 1.10), 2), d,
                'Reposição semestral de estacas', 'Fixo', 'Manutenção')
            mov(p_sal, 'entrada', 110, round(random.uniform(97, 103), 2), d,
                'Reposição semestral de sal/proteinado', 'Variavel', 'Nutrição')
        if d.month in (1, 7):
            mov(p_arame, 'entrada', 6, round(random.uniform(290, 320), 2), d,
                'Reposição semestral de arame', 'Fixo', 'Manutenção')
        d = (d.replace(day=1) + timedelta(days=32)).replace(day=15)

    print(f"      {len(estoque_mov_rows)} movimentações de insumos programadas "
          f"(estaca/arame/sal — aftosa/anabólico entram na etapa de sanidade)")

    # ══════════════════════════════════════════════════════════════
    # [5/13] REBANHO FUNDADOR — matrizes e touros
    # ══════════════════════════════════════════════════════════════
    print("[5/13] Fundando rebanho reprodutor (matrizes e touros)...")

    def cadastra_reprodutor(brinco, sexo, peso, data_entrada, raca_nome='Nelore'):
        compra_arroba, _ = preco_arroba(data_entrada)
        preco = round((peso / ARROBA_KG) * compra_arroba, 2)
        cur.execute(
            "INSERT INTO animais (brinco, sexo, raca, data_compra, data_nascimento, preco_compra, user_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (brinco, sexo, raca_nome, data_entrada, data_entrada, preco, uid)
        )
        aid = cur.lastrowid
        registrar_caixa(data_entrada, -preco, 'compra_gado')
        _, data_morte = resolve_destino(data_entrada, None)
        gmd_estavel = round(clamp(random.gauss(0.05, 0.02), 0.0, 0.10), 3)  # mantença, não engorda
        registra_crescimento(aid, peso, data_entrada, gmd_estavel, data_morte or END, passo=180)
        return {'id': aid, 'brinco': brinco, 'entrada': data_entrada, 'data_morte': data_morte}

    matriz_pool = []
    touro_pool = []
    n_obitos_fundadoras = 0
    _matriz_seq = 0
    _touro_seq = 0

    def compra_matrizes(qtd, data_entrada):
        """Compra `qtd` matrizes adultas (já elegíveis para cobertura desde a entrada) na
        data dada. Usado tanto na fundação (dia 1) quanto nas ondas de expansão do rebanho
        reprodutivo — comprar uma matriz não é diferente de comprar um lote, exceto que ela
        entra direto no plantel de reprodução em vez de ir para o pipeline de engorda."""
        global _matriz_seq, n_obitos_fundadoras
        for _ in range(qtd):
            _matriz_seq += 1
            peso = round(random.gauss(450, 20), 2)
            m = cadastra_reprodutor(f"MTZ-{_matriz_seq:03d}", 'F', peso, data_entrada)
            if m['data_morte'] is None:
                m['ativa'] = True
                m['elegivel_desde'] = data_entrada
                matriz_pool.append(m)
            else:
                n_obitos_fundadoras += 1
                custos_rows.append((uid, 'Perda', 'Mortalidade', 0.00, m['data_morte'],
                                     f"Óbito animal id={m['id']} - Causa: {random.choice(MORTE_CAUSAS)}"))
                cur.execute("UPDATE animais SET data_venda=%s, preco_venda=0.00 WHERE id=%s",
                            (m['data_morte'], m['id']))
        conn.commit()

    def compra_touros(qtd, data_entrada, raca_nome='Nelore'):
        global _touro_seq
        for _ in range(qtd):
            _touro_seq += 1
            peso = round(random.gauss(560, 25), 2)
            t = cadastra_reprodutor(f"TOU-{_touro_seq:02d}", 'M', peso, data_entrada, raca_nome)
            touro_pool.append(t)
        conn.commit()

    # Fundação (dia 1): plantel pequeno para não estourar o caixa da carência (Vale da Morte).
    compra_matrizes(12, START)
    compra_touros(3, START)

    # Ondas de expansão: o plantel reprodutivo cresce nos anos seguintes, financiado pela
    # margem já consolidada da engorda comercial (2022+ tem ~47% de margem, folga ampla) —
    # não pelo aporte inicial. Sem isso, "nascidos na fazenda" fica muito abaixo dos ~20%
    # pedidos, porque o pipeline comercial (~200 cabeças/ano) domina o total de animais.
    compra_matrizes(35, date(2022, 1, 15))
    compra_touros(3, date(2022, 1, 15))
    compra_matrizes(35, date(2023, 1, 15))
    compra_matrizes(18, date(2024, 1, 15))
    t3 = cadastra_reprodutor('TOU-EXT', 'M', round(random.gauss(570, 20), 2), date(2023, 3, 1), 'Angus')
    touro_pool.append(t3)
    conn.commit()

    print(f"      {len(matriz_pool)} matrizes ativas + {len(touro_pool)} touros "
          f"(fundação + ondas de expansão 2022-2024; {n_obitos_fundadoras} óbitos no plantel reprodutivo)")

    # ══════════════════════════════════════════════════════════════
    # [6/13] PIPELINE COMERCIAL — compra/venda de lotes de 20 cabeças
    # ══════════════════════════════════════════════════════════════
    print("[6/13] Simulando pipeline comercial (carência + regime estável)...")

    lote_seq = 0
    wip = []  # fila FIFO de lotes comprados e ainda não vendidos
    sales_log = []  # (data, cabecas_vendidas) para o resumo final
    n_obitos_comercial = 0

    def criar_lote_comercial(data_compra, boosted=False):
        global lote_seq
        lote_seq += 1
        codigo = f"REP-{lote_seq:03d}"
        compra_arroba, _ = preco_arroba(data_compra)
        pesos = [round(random.uniform(9.5, 10.0) if boosted else random.uniform(8.0, 10.0), 2) * ARROBA_KG
                 for _ in range(LOTE_SIZE)]
        precos = [round((p / ARROBA_KG) * compra_arroba, 2) for p in pesos]
        sexos = [('M' if random.random() < 0.80 else 'F') for _ in range(LOTE_SIZE)]
        custo_medio = round(sum(precos) / len(precos), 2)

        cur.execute(
            "INSERT INTO lotes (user_id, codigo_lote, descricao, data_aquisicao, custo_medio_cabeca) "
            "VALUES (%s, %s, %s, %s, %s)",
            (uid, codigo, 'Reposição - lote fundador' if boosted else 'Reposição para engorda',
             data_compra, custo_medio)
        )
        lote_id = cur.lastrowid

        rows = [(f"{codigo}-{i + 1:02d}", sexos[i], raca(), data_compra, precos[i], uid, lote_id)
                for i in range(LOTE_SIZE)]
        cur.executemany(
            "INSERT INTO animais (brinco, sexo, raca, data_compra, preco_compra, user_id, lote_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)", rows
        )
        conn.commit()
        cur.execute("SELECT id FROM animais WHERE lote_id = %s ORDER BY id", (lote_id,))
        ids = [r[0] for r in cur.fetchall()]

        for preco in precos:
            registrar_caixa(data_compra, -preco, 'compra_gado')

        animais_lote = [{'id': aid, 'peso_compra': peso, 'data_compra': data_compra,
                          'gmd': sorteia_gmd(), 'sexo': sexo}
                         for aid, peso, sexo in zip(ids, pesos, sexos)]
        return {'lote_id': lote_id, 'codigo': codigo, 'data_compra': data_compra, 'animais': animais_lote}

    def processar_lote(cohort, data_venda_planejada):
        """Para cada animal: resolve morte-antes-da-venda x venda, grava pesagens/atualizações."""
        global n_obitos_comercial
        _, venda_arroba = preco_arroba(data_venda_planejada)
        updates_venda, updates_obito = [], []
        for a in cohort['animais']:
            destino, data_destino = resolve_destino(a['data_compra'], data_venda_planejada)
            if destino == 'morte':
                registra_crescimento(a['id'], a['peso_compra'], a['data_compra'], a['gmd'], data_destino)
                updates_obito.append((data_destino, 0.00, a['id']))
                causa = random.choice(MORTE_CAUSAS)
                custos_rows.append((uid, 'Perda', 'Mortalidade', 0.00, data_destino,
                                     f"Óbito animal id={a['id']} - Causa: {causa}"))
                n_obitos_comercial += 1
            else:
                peso_final = registra_crescimento(a['id'], a['peso_compra'], a['data_compra'],
                                                   a['gmd'], data_venda_planejada)
                preco_venda = round((peso_final / ARROBA_KG) * venda_arroba, 2)
                updates_venda.append((data_venda_planejada, preco_venda, a['id']))
                registrar_caixa(data_venda_planejada, preco_venda, 'venda')
        if updates_venda:
            cur.executemany("UPDATE animais SET data_venda=%s, preco_venda=%s WHERE id=%s", updates_venda)
        if updates_obito:
            cur.executemany("UPDATE animais SET data_venda=%s, preco_venda=%s WHERE id=%s", updates_obito)
        conn.commit()
        sales_log.append((data_venda_planejada, len(updates_venda)))
        return len(updates_venda)

    def finalizar_lote_aberto(cohort):
        """Lotes ainda em curral no fim da simulação: resolve morte x sobrevivência até END."""
        global n_obitos_comercial
        updates_obito = []
        for a in cohort['animais']:
            destino, data_destino = resolve_destino(a['data_compra'], None)
            if destino == 'morte':
                registra_crescimento(a['id'], a['peso_compra'], a['data_compra'], a['gmd'], data_destino)
                updates_obito.append((data_destino, 0.00, a['id']))
                causa = random.choice(MORTE_CAUSAS)
                custos_rows.append((uid, 'Perda', 'Mortalidade', 0.00, data_destino,
                                     f"Óbito animal id={a['id']} - Causa: {causa}"))
                n_obitos_comercial += 1
            else:
                registra_crescimento(a['id'], a['peso_compra'], a['data_compra'], a['gmd'], END)
        if updates_obito:
            cur.executemany("UPDATE animais SET data_venda=%s, preco_venda=%s WHERE id=%s", updates_obito)
            conn.commit()

    # --- Fase 1: carência (cadência lenta, sem vendas) ---
    founder = criar_lote_comercial(START, boosted=True)
    peso_medio_founder = sum(a['peso_compra'] for a in founder['animais']) / LOTE_SIZE
    dias_ate_20arroba = int((20 * ARROBA_KG - peso_medio_founder) / FOUNDER_GMD_ALVO)
    data_primeira_venda = START + timedelta(days=dias_ate_20arroba)
    wip.append(founder)

    data_compra_cursor = START
    while True:
        data_compra_cursor += timedelta(days=random.randint(46, 54))
        if data_compra_cursor >= data_primeira_venda:
            break
        wip.append(criar_lote_comercial(data_compra_cursor))

    print(f"      Carência: {len(wip)} lotes comprados até a 1ª venda "
          f"({dias_ate_20arroba} dias / {dias_ate_20arroba / 30.4:.1f} meses)")

    processar_lote(wip.pop(0), data_primeira_venda)
    data_ultima_venda = data_primeira_venda

    # --- Fase 2: regime estável (venda ~36 dias, compra 5-7 dias após, ramp-up de WIP) ---
    # O ramp-up (compra de lotes extras até atingir TARGET_WIP) só começa no ano seguinte ao da
    # 1ª venda: no próprio ano da 1ª venda a receita ainda está começando a fluir (poucos meses
    # de vendas), então qualquer compra extra nesse ano é puro custo sem receita correspondente
    # e derruba a margem abaixo de 30% — a regra de negócio exige ≥30% em todo ano após o 1º.
    ramp_ate = data_primeira_venda + timedelta(days=548)  # ~18 meses de ramp-up de WIP
    ano_ramp_liberado = data_primeira_venda.year + 1
    while data_ultima_venda < END:
        proxima_venda = data_ultima_venda + timedelta(days=random.randint(34, 39))
        if proxima_venda > END:
            break

        data_compra_reposicao = data_ultima_venda + timedelta(days=random.randint(5, 7))
        wip.append(criar_lote_comercial(data_compra_reposicao))

        if (len(wip) < TARGET_WIP and proxima_venda <= ramp_ate
                and data_compra_reposicao.year >= ano_ramp_liberado):
            data_extra = data_compra_reposicao + timedelta(days=random.randint(10, 16))
            if data_extra < END:
                wip.append(criar_lote_comercial(data_extra))

        if wip:
            processar_lote(wip.pop(0), proxima_venda)
        data_ultima_venda = proxima_venda

    for lote_aberto in wip:
        finalizar_lote_aberto(lote_aberto)

    print(f"      {lote_seq} lotes comerciais comprados, {len(sales_log)} vendas realizadas, "
          f"{n_obitos_comercial} óbitos no pipeline comercial, "
          f"{len(wip)} lotes ainda em curral no fim da simulação")

    # ══════════════════════════════════════════════════════════════
    # [7/13] REPRODUÇÃO — coberturas, partos, crescimento da fazenda
    # ══════════════════════════════════════════════════════════════
    print("[7/13] Simulando reprodução e nascimentos na fazenda...")

    born_seq = 0
    _counter = 0
    pending = []  # heap (data, counter, ref_dict)
    n_obitos_cria = 0

    for cow in matriz_pool:
        _counter += 1
        heapq.heappush(pending, (cow['elegivel_desde'], _counter, cow))

    def touro_disponivel(d):
        disponiveis = [t for t in touro_pool if t['entrada'] <= d and (t['data_morte'] is None or d <= t['data_morte'])]
        return random.choice(disponiveis) if disponiveis else None

    while pending:
        d, _, cow = heapq.heappop(pending)
        if d > (cow['data_morte'] or END):
            continue

        touro = touro_disponivel(d)
        touro_id = touro['id'] if touro and random.random() > 0.15 else None
        touro_externo_txt = None if touro_id else 'Central de IA - Sêmen Externo'

        roll = random.random()
        if roll < 0.82:
            resultado = 'vivo'
        elif roll < 0.90:
            resultado = 'aborto'
        else:
            resultado = 'natimorto'

        data_parto_prevista = d + timedelta(days=285)
        gestacao_em_curso = resultado == 'vivo' and data_parto_prevista > END
        data_parto = None if gestacao_em_curso else (
            d + timedelta(days=random.randint(278, 292)) if resultado in ('vivo', 'natimorto') else None)

        if resultado == 'aborto':
            # data_parto fica NULL (sem nascimento) — se diagnostico='positivo' aqui, a
            # vw_partos_previstos (que só filtra por data_parto IS NULL) mostraria um "parto
            # previsto" falso para uma gestação que já se perdeu. Mantém 'pendente'/NULL.
            diagnostico, data_diagnostico = 'pendente', None
        elif gestacao_em_curso:
            dg_data = d + timedelta(days=random.randint(25, 40))
            diagnostico, data_diagnostico = ('positivo', dg_data) if dg_data <= END else ('pendente', None)
        else:
            diagnostico, data_diagnostico = 'positivo', d + timedelta(days=random.randint(25, 40))

        reproducao_rows.append((uid, cow['id'], touro_id, touro_externo_txt, d, data_parto, resultado,
                                 diagnostico, data_diagnostico, data_parto_prevista))

        if resultado == 'vivo' and data_parto and data_parto <= END:
            born_seq += 1
            sexo = 'M' if random.random() < 0.5 else 'F'
            peso_nasc = round(clamp(random.gauss(34 if sexo == 'M' else 31, 3), 22, 45), 2)
            brinco = f"CRI-{born_seq:04d}"
            cur.execute(
                "INSERT INTO animais (brinco, sexo, raca, data_nascimento, mae_id, pai_id, user_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (brinco, sexo, 'Nelore', data_parto, cow['id'], touro_id, uid)
            )
            calf_id = cur.lastrowid
            conn.commit()

            retida = sexo == 'F' and random.random() < 0.55
            if retida:
                destino, data_morte = resolve_destino(data_parto, None)
                gmd_cria = sorteia_gmd()
                if destino == 'morte':
                    registra_crescimento(calf_id, peso_nasc, data_parto, gmd_cria, data_morte)
                    cur.execute("UPDATE animais SET data_venda=%s, preco_venda=0.00 WHERE id=%s",
                                (data_morte, calf_id))
                    causa = random.choice(MORTE_CAUSAS)
                    custos_rows.append((uid, 'Perda', 'Mortalidade', 0.00, data_morte,
                                         f"Óbito animal id={calf_id} - Causa: {causa}"))
                    n_obitos_cria += 1
                else:
                    registra_crescimento(calf_id, peso_nasc, data_parto, gmd_cria, END,
                                         passo=180, peso_max=480.0)
                    nova_matriz = {'id': calf_id, 'brinco': brinco, 'entrada': data_parto,
                                    'data_morte': None, 'ativa': True,
                                    'elegivel_desde': data_parto + timedelta(days=730)}
                    matriz_pool.append(nova_matriz)
                    _counter += 1
                    heapq.heappush(pending, (nova_matriz['elegivel_desde'], _counter, nova_matriz))
            else:
                gmd_cria = sorteia_gmd()
                alvo_kg = round(random.uniform(20.0, 22.0), 2) * ARROBA_KG
                dias_cria = max(1, int((alvo_kg - peso_nasc) / gmd_cria))
                data_venda_prevista = data_parto + timedelta(days=dias_cria)
                destino, data_destino = resolve_destino(data_parto, data_venda_prevista)
                if destino == 'morte':
                    registra_crescimento(calf_id, peso_nasc, data_parto, gmd_cria, data_destino)
                    cur.execute("UPDATE animais SET data_venda=%s, preco_venda=0.00 WHERE id=%s",
                                (data_destino, calf_id))
                    causa = random.choice(MORTE_CAUSAS)
                    custos_rows.append((uid, 'Perda', 'Mortalidade', 0.00, data_destino,
                                         f"Óbito animal id={calf_id} - Causa: {causa}"))
                    n_obitos_cria += 1
                elif data_destino and data_destino <= END:
                    peso_final = registra_crescimento(calf_id, peso_nasc, data_parto, gmd_cria, data_destino)
                    _, venda_arroba = preco_arroba(data_destino)
                    preco_venda = round((peso_final / ARROBA_KG) * venda_arroba, 2)
                    cur.execute("UPDATE animais SET data_venda=%s, preco_venda=%s WHERE id=%s",
                                (data_destino, preco_venda, calf_id))
                    registrar_caixa(data_destino, preco_venda, 'venda')
                else:
                    registra_crescimento(calf_id, peso_nasc, data_parto, gmd_cria, END)
            conn.commit()

        proximo = d + timedelta(days=random.randint(355, 395))
        if proximo <= (cow['data_morte'] or END):
            _counter += 1
            heapq.heappush(pending, (proximo, _counter, cow))

    print(f"      {len(reproducao_rows)} coberturas, {born_seq} nascimentos na fazenda, "
          f"{n_obitos_cria} óbitos entre crias "
          f"({len(matriz_pool) - 10} novilhas incorporadas como futuras matrizes)")

    # ══════════════════════════════════════════════════════════════
    # [8/13] MEDICAÇÕES — febre aftosa anual + anabólico trimestral (machos vivos)
    # ══════════════════════════════════════════════════════════════
    print("[8/13] Gerando medicações (aftosa + anabólico)...")

    cur.execute(
        "SELECT id, sexo, data_compra, data_nascimento, data_venda FROM animais WHERE user_id = %s", (uid,)
    )
    todos = cur.fetchall()

    aftosa_por_data, anab_por_data = {}, {}
    for aid, sexo, dc, dn, dv in todos:
        entrada = dc or dn
        if not entrada:
            continue
        saida = dv or END
        for ano in range(entrada.year, min(saida.year, END.year) + 1):
            dt = date(ano, 5, 15)
            if entrada <= dt <= saida:
                medicacoes_rows.append((aid, dt, 'Febre Aftosa', 1.20, None))
                aftosa_por_data[dt] = aftosa_por_data.get(dt, 0) + 1
        if sexo == 'M':
            for ano in range(entrada.year, min(saida.year, END.year) + 1):
                for mes in (1, 5, 9):
                    dt = date(ano, mes, 20)
                    if entrada <= dt <= saida:
                        medicacoes_rows.append((aid, dt, 'Anabólico', 2.00, None))
                        anab_por_data[dt] = anab_por_data.get(dt, 0) + 1
                        registrar_caixa(dt, -2.00, 'sanidade')

    for dt, qtd in aftosa_por_data.items():
        mov(p_aftosa, 'entrada', qtd, 1.20, dt - timedelta(days=5), 'Compra para aplicação anual')
        mov(p_aftosa, 'saida', qtd, None, dt, 'Vacinação do rebanho')
        registrar_caixa(dt, -round(qtd * 1.20, 2), 'sanidade')
    for dt, qtd in anab_por_data.items():
        mov(p_anab, 'entrada', qtd, 2.00, dt - timedelta(days=5), 'Compra para aplicação trimestral')
        mov(p_anab, 'saida', qtd, None, dt, 'Aplicação em machos ativos')

    print(f"      {len(medicacoes_rows)} medicações programadas")

    # ══════════════════════════════════════════════════════════════
    # [9/13] FOLHA DE PAGAMENTO
    # ══════════════════════════════════════════════════════════════
    print("[9/13] Lançando folha de pagamento mensal...")

    d = date(START.year, START.month, 5)
    while d <= END:
        custos_rows.append((uid, 'Fixo', 'Salário', VAQUEIRO_SALARIO, d, 'Salário mensal - Vaqueiro'))
        custos_rows.append((uid, 'Fixo', 'Salário', float(SALARIO_MINIMO[d.year]), d,
                             'Salário mensal - Cerqueiro (salário mínimo vigente)'))
        registrar_caixa(d, -(VAQUEIRO_SALARIO + SALARIO_MINIMO[d.year]), 'folha')
        d = (d.replace(day=1) + timedelta(days=32)).replace(day=5)

    print(f"      {len(custos_rows)} lançamentos de custos operacionais no total")

    # ══════════════════════════════════════════════════════════════
    # [10/13] OCUPAÇÕES — snapshot de alocação em pasto (situação atual)
    # ══════════════════════════════════════════════════════════════
    print("[10/13] Alocando rebanho ativo nos pastos (snapshot atual)...")

    cur.execute(
        "SELECT id, sexo FROM animais WHERE user_id = %s AND data_venda IS NULL AND deleted_at IS NULL", (uid,)
    )
    ativos_final = cur.fetchall()
    machos_ativos = [aid for aid, sexo in ativos_final if sexo == 'M']
    femeas_ativas = [aid for aid, sexo in ativos_final if sexo == 'F']
    random.shuffle(machos_ativos)

    DATA_ENTRADA = END - timedelta(days=45)
    grupos_machos = [machos_ativos[i::4] for i in range(4)]  # 4 piquetes de engorda
    alocacoes = list(zip(modulos[:4], grupos_machos)) + ([(modulos[5], femeas_ativas)] if len(modulos) > 5 else [])

    for modulo_id, ids in alocacoes:
        if not ids:
            continue
        cur.execute("INSERT INTO ocupacoes (modulo_id, user_id, data_entrada) VALUES (%s, %s, %s)",
                    (modulo_id, uid, DATA_ENTRADA))
        occ_id = cur.lastrowid
        cur.executemany("INSERT INTO ocupacao_animais (ocupacao_id, animal_id) VALUES (%s, %s)",
                         [(occ_id, aid) for aid in ids])
    conn.commit()

    # ══════════════════════════════════════════════════════════════
    # [11/13] BULK INSERT — pesagens, medicações, custos, reprodução, estoque
    # ══════════════════════════════════════════════════════════════
    print("[11/13] Gravando registros em lote...")
    bulk("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", pesagens_rows)
    print(f"      {len(pesagens_rows)} pesagens")
    bulk("INSERT INTO medicacoes (animal_id, data_aplicacao, nome_medicamento, custo, observacoes) "
         "VALUES (%s, %s, %s, %s, %s)", medicacoes_rows)
    print(f"      {len(medicacoes_rows)} medicações")
    bulk("INSERT INTO custos_operacionais (user_id, categoria, tipo_custo, valor, data_custo, descricao) "
         "VALUES (%s, %s, %s, %s, %s, %s)", custos_rows)
    print(f"      {len(custos_rows)} custos operacionais")
    bulk("INSERT INTO reproducao (user_id, vaca_id, touro_id, touro_externo, data_cobertura, data_parto, "
         "resultado, diagnostico, data_diagnostico, data_parto_prevista) "
         "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", reproducao_rows)
    print(f"      {len(reproducao_rows)} registros de reprodução")
    bulk("INSERT INTO estoque_movimentacoes (user_id, produto_id, tipo, quantidade, custo_unitario, motivo, "
         "data_mov) VALUES (%s, %s, %s, %s, %s, %s, %s)", estoque_mov_rows)
    print(f"      {len(estoque_mov_rows)} movimentações de estoque")

    # ══════════════════════════════════════════════════════════════
    # [12/13] RELATÓRIO ANO A ANO — receita, despesas, vendas, lucro, margem
    # ══════════════════════════════════════════════════════════════
    print("\n[12/13] Relatório financeiro ano a ano:")
    anos = list(range(START.year, END.year + 1))
    por_ano = {a: {'venda': 0.0, 'compra_gado': 0.0, 'estoque': 0.0, 'folha': 0.0,
                    'sanidade': 0.0, 'aporte': 0.0} for a in anos}
    for d, v, cat in caixa_ledger:
        por_ano[d.year][cat] += v
    vendas_por_ano = {a: 0 for a in anos}
    for d, qtd in sales_log:
        vendas_por_ano[d.year] += qtd

    print(f"{'Ano':<6}{'Receita':>14}{'Compra Gado':>14}{'Nutrição/Infra':>16}"
          f"{'Folha':>12}{'Sanidade':>10}{'Vendas':>8}{'Lucro':>14}{'Margem':>9}")
    for a in anos:
        r = por_ano[a]
        receita = r['venda']
        despesas = -(r['compra_gado'] + r['estoque'] + r['folha'] + r['sanidade'])
        lucro = receita - despesas
        margem = (lucro / receita * 100) if receita > 0 else None
        margem_str = f"{margem:6.1f}%" if margem is not None else "   n/a"
        print(f"{a:<6}{receita:>14,.2f}{-r['compra_gado']:>14,.2f}{-r['estoque']:>16,.2f}"
              f"{-r['folha']:>12,.2f}{-r['sanidade']:>10,.2f}{vendas_por_ano[a]:>8}{lucro:>14,.2f}{margem_str:>9}")
        if a > START.year and margem is not None and margem < 30:
            print(f"      ALERTA: margem de {a} abaixo de 30% (regra exige ≥30% após o 1º ano).")

    # ══════════════════════════════════════════════════════════════
    # [13/13] RESUMO E VALIDAÇÃO DE CAIXA
    # ══════════════════════════════════════════════════════════════
    caixa_ordenado = sorted(caixa_ledger, key=lambda x: x[0])
    saldo = 0.0
    saldo_minimo = None  # None até a 1ª transação — 0.0 como sentinela mascarava o mínimo real
    data_minimo = START
    for d, v, _ in caixa_ordenado:
        saldo += v
        if saldo_minimo is None or saldo < saldo_minimo:
            saldo_minimo = saldo
            data_minimo = d
    saldo_minimo = saldo_minimo if saldo_minimo is not None else 0.0

    cur.execute("SELECT COUNT(*) FROM animais WHERE user_id=%s AND data_venda IS NULL AND deleted_at IS NULL", (uid,))
    n_ativos_f = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM animais WHERE user_id=%s AND sexo='M' AND data_venda IS NULL AND deleted_at IS NULL", (uid,))
    n_machos_f = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM animais WHERE user_id=%s AND sexo='F' AND data_venda IS NULL AND deleted_at IS NULL", (uid,))
    n_femeas_f = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM animais WHERE user_id=%s AND data_venda IS NOT NULL AND preco_venda > 0", (uid,))
    n_vendidos_f = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM animais WHERE user_id=%s AND data_venda IS NOT NULL AND preco_venda = 0", (uid,))
    n_mortos_f = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM animais WHERE user_id=%s AND data_nascimento IS NOT NULL", (uid,))
    n_nascidos_f = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM animais WHERE user_id=%s", (uid,))
    n_total_f = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM animais WHERE user_id=%s AND sexo='M'", (uid,))
    n_machos_total = cur.fetchone()[0]

    print(f"""
╔════════════════════════════════════════════════════════════════╗
║  Conta demonstracao — histórico 2020-01-01 a 2026-06-30         ║
╠════════════════════════════════════════════════════════════════╣
║  Rebanho ativo hoje : {n_ativos_f:<5}  (M {n_machos_f} / F {n_femeas_f} = """
          f"""{100*n_femeas_f/max(1,n_ativos_f):.1f}% fêmeas)
║  Total já vendido   : {n_vendidos_f:<5}
║  Total de óbitos    : {n_mortos_f:<5}  ({100*n_mortos_f/max(1,n_total_f):.1f}% do total cadastrado)
║  Total já cadastrado: {n_total_f:<5}  (M {100*n_machos_total/max(1,n_total_f):.1f}% / F {100*(n_total_f-n_machos_total)/max(1,n_total_f):.1f}%)
║  Nascidos na fazenda: {n_nascidos_f:<5}  ({100*n_nascidos_f/max(1,n_total_f):.1f}% do total)
╠════════════════════════════════════════════════════════════════╣
║  Vendas em lote comercial: {len(sales_log):<5}
║  Cabeças/ano (aprox, regime estável): {sum(q for _, q in sales_log)/((END.year - data_primeira_venda.year) or 1):.0f}
╠════════════════════════════════════════════════════════════════╣
║  Saldo de caixa mínimo atingido: R$ {saldo_minimo:,.2f}  (em {data_minimo})
║  Saldo de caixa final (30/06/2026): R$ {saldo:,.2f}
╚════════════════════════════════════════════════════════════════╝
""")
    if saldo_minimo < 0:
        print(f"  ATENÇÃO: caixa ficou negativo em R$ {abs(saldo_minimo):,.2f} — ajuste parâmetros de preço/cadência.")
    else:
        print("  Caixa nunca ficou negativo — aporte cobriu integralmente o Vale da Morte do 1º ciclo.")

    conn.commit()
    print("\n[13/13] Concluído com sucesso.")

except Exception as exc:
    conn.rollback()
    print(f"\nERRO — transação revertida (rollback), nenhum dado parcial foi gravado: {exc}")
    raise
finally:
    cur.close()
    conn.close()
