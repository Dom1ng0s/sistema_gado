#!/usr/bin/env python3
"""
Seed histórico: conta demonstracao — simulação econômica completa 2020-01-01 a 2026-06-30

Reconstrói do zero os dados de gestão vinculados ao usuário 'demonstracao' (não altera
usuarios/configuracoes). Usa mysql.connector puro — este projeto não usa SQLAlchemy/ORM
(ver CLAUDE.md: "SQL puro — não introduzir SQLAlchemy ou ORM").

Premissas econômicas (ver Passo Zero na conversa que gerou este script):
  - Carência: lote fundador entra a 9,5-10@ e é vendido ao atingir 20@ (gatilho por peso,
    não por data fixa). Com GMD ~0,90-0,95 isso pousa em ~330-350 dias.
  - Cadência de compra ~46-54 dias durante a carência (mais lenta que os 36 dias do regime
    estável) para não estourar o aporte de R$600.000 antes da 1ª receita.
  - Regime estável: vendas a cada ~36 dias, compra de reposição 5-7 dias após cada venda,
    com ramp-up de WIP (lotes simultaneamente em curral) nos primeiros ~18 meses pós-1ª-venda
    — autofinanciado pela margem das vendas, não pelo aporte.
  - Aporte de capital modelado como custos_operacionais com valor NEGATIVO (categoria='Aporte')
    — é o único jeito de representar uma entrada de caixa avulsa neste schema, que só tem
    receita nativa via animais.preco_venda. Isso soma corretamente em v_fluxo_caixa.
  - Mortalidade: sem coluna de status em `animais`. Modelada como data_venda=data_óbito,
    preco_venda=0.00 (sai de "ativos", não gera receita, preco_compra continua contabilizado
    como custo já incorrido) + 1 linha de custos_operacionais (valor=0) para rastreabilidade
    da causa.

Rodar:
    python seed_demo_historico.py
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
TARGET_WIP = 11  # lotes simultaneamente em curral no regime estável maduro

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

caixa_ledger = []  # (data, valor_assinado) — só para validação/print, não vai ao banco


def registrar_caixa(d, valor):
    caixa_ledger.append((d, valor))


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def rdate(s, e):
    return s + timedelta(days=random.randint(0, max(0, (e - s).days)))


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


def gmd_normal():
    return round(clamp(random.gauss(0.87, 0.06), 0.70, 1.05), 3)


def gmd_ruim():
    return round(random.uniform(0.20, 0.40), 3)


def gmd_excecional():
    return round(random.uniform(1.30, 1.60), 3)


def bulk(sql, rows, chunk=500):
    if not rows:
        return
    for i in range(0, len(rows), chunk):
        cur.executemany(sql, rows[i:i + chunk])
    conn.commit()


# ══════════════════════════════════════════════════════════════════
# [0/12] USUÁRIO — localizar (NÃO alterar usuarios/configuracoes)
# ══════════════════════════════════════════════════════════════════
print("[0/12] Localizando usuário 'demonstracao'...")
cur.execute("SELECT id FROM usuarios WHERE LOWER(username) = LOWER(%s)", ('demonstracao',))
row = cur.fetchone()
if not row:
    raise SystemExit("Usuário 'demonstracao' não encontrado. Crie a conta antes de rodar este seed.")
uid = row[0]
print(f"     uid={uid}")

# ══════════════════════════════════════════════════════════════════
# [1/12] LIMPEZA — apaga dados de gestão vinculados ao user_id
# ══════════════════════════════════════════════════════════════════
print("[1/12] Limpando dados de gestão anteriores...")
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
print(f"     {len(old_aids)} animais antigos removidos")

# ══════════════════════════════════════════════════════════════════
# [2/12] APORTE DE CAPITAL INICIAL
# ══════════════════════════════════════════════════════════════════
print("[2/12] Lançando aporte de capital inicial (R$ 600.000,00)...")
cur.execute(
    "INSERT INTO custos_operacionais (user_id, categoria, tipo_custo, valor, data_custo, descricao) "
    "VALUES (%s, %s, %s, %s, %s, %s)",
    (uid, 'Aporte', 'Capital Inicial', -600000.00, START,
     'Aporte de Capital Inicial - Sócios (financia o Vale da Morte do 1º ciclo)')
)
conn.commit()
registrar_caixa(START, 600000.00)

# ══════════════════════════════════════════════════════════════════
# [3/12] PASTOS
# ══════════════════════════════════════════════════════════════════
print("[3/12] Criando pastos...")
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
print(f"     {len(modulos)} módulos criados")

# ══════════════════════════════════════════════════════════════════
# [4/12] ESTOQUE — produtos + saldo inicial (Jan/2020)
# ══════════════════════════════════════════════════════════════════
print("[4/12] Criando produtos de estoque e saldo inicial...")


def criar_produto(nome, unidade, categoria, minimo):
    cur.execute(
        "INSERT INTO estoque_produtos (user_id, nome, unidade, categoria, estoque_minimo) "
        "VALUES (%s, %s, %s, %s, %s)", (uid, nome, unidade, categoria, minimo)
    )
    return cur.lastrowid


p_estaca = criar_produto('Estaca de Madeira', 'unidade', 'outro', 80)
p_arame = criar_produto('Arame Farpado (rolo 250m)', 'rolo', 'outro', 2)
p_sal = criar_produto('Sal Mineral (saco 30kg)', 'saco', 'mineral', 10)
p_aftosa = criar_produto('Vacina Febre Aftosa', 'dose', 'vacina', 50)
p_anab = criar_produto('Anabólico Bovino', 'dose', 'medicamento', 30)
conn.commit()

estoque_mov_rows = []


def mov(pid, tipo, qtd, custo_unit, data, motivo):
    estoque_mov_rows.append((uid, pid, tipo, qtd, custo_unit, motivo, data))
    if tipo == 'entrada' and custo_unit:
        registrar_caixa(data, -round(qtd * custo_unit, 2))


mov(p_estaca, 'entrada', 100, 1.00, START, 'Saldo inicial')
mov(p_arame, 'entrada', 2, 300.00, START, 'Saldo inicial')
mov(p_sal, 'entrada', 4, 50.00, START, 'Saldo inicial')

# consumo distribuído nos meses (500 estacas/ano, 10 arames/ano, 100 sacos de sal/ano)
d = date(START.year, START.month, 15)
while d <= END:
    estacas_qtd = 500 // 12 + (1 if d.month <= 500 % 12 else 0)
    sal_qtd = 100 // 12 + (1 if d.month <= 100 % 12 else 0)
    mov(p_estaca, 'saida', estacas_qtd, None, d, 'Consumo mensal de manutenção de cercas')
    mov(p_sal, 'saida', sal_qtd, None, d, 'Consumo mensal do rebanho')
    if d.month in (2, 5, 8, 11):
        mov(p_arame, 'saida', random.randint(2, 3), None, d, 'Reforma de cercas')
    if d.month in (3, 9):
        mov(p_estaca, 'entrada', 250, round(random.uniform(0.95, 1.10), 2), d, 'Reposição semestral')
        mov(p_sal, 'entrada', 55, round(random.uniform(48, 55), 2), d, 'Reposição semestral')
    if d.month in (1, 7):
        mov(p_arame, 'entrada', 6, round(random.uniform(290, 320), 2), d, 'Reposição semestral')
    d = (d.replace(day=1) + timedelta(days=32)).replace(day=15)

print(f"     {len(estoque_mov_rows)} movimentações de insumos programadas")

# ══════════════════════════════════════════════════════════════════
# [5/12] REBANHO FUNDADOR — matrizes e touros
# ══════════════════════════════════════════════════════════════════
print("[5/12] Fundando rebanho reprodutor (matrizes e touros)...")

lotes_rows_cache = []  # não usado para matriz/touro (lote_id fica NULL — não são gado comercial)

matriz_rows = []
for i in range(10):
    peso = round(random.gauss(450, 20), 2)
    compra, _ = preco_arroba(START)
    preco = round((peso / ARROBA_KG) * compra, 2)
    matriz_rows.append((f"MTZ-{i + 1:03d}", 'F', 'Nelore', START, START, preco, uid))
    registrar_caixa(START, -preco)

touro_rows = []
for i in range(2):
    peso = round(random.gauss(560, 25), 2)
    compra, _ = preco_arroba(START)
    preco = round((peso / ARROBA_KG) * compra, 2)
    touro_rows.append((f"TOU-{i + 1:02d}", 'M', 'Nelore', START, START, preco, uid))
    registrar_caixa(START, -preco)

bulk(
    "INSERT INTO animais (brinco, sexo, raca, data_compra, data_nascimento, preco_compra, user_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
    [(b, s, r, dc, dc, p, u) for b, s, r, dc, _, p, u in matriz_rows]
)
cur.execute("SELECT id, brinco FROM animais WHERE user_id = %s AND brinco LIKE 'MTZ-%' ORDER BY id", (uid,))
matriz_id_by_brinco = {b: i for i, b in cur.fetchall()}

bulk(
    "INSERT INTO animais (brinco, sexo, raca, data_compra, data_nascimento, preco_compra, user_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
    [(b, s, r, dc, dc, p, u) for b, s, r, dc, _, p, u in touro_rows]
)
cur.execute("SELECT id, brinco FROM animais WHERE user_id = %s AND brinco LIKE 'TOU-%' ORDER BY id", (uid,))
touro_id_by_brinco = {b: i for i, b in cur.fetchall()}
touro_pool = [{'id': i, 'brinco': b, 'ativo': True} for b, i in touro_id_by_brinco.items()]

# terceiro touro entra em 2023 para diversidade genética / ranking de touros
_touro3_peso = round(random.gauss(570, 20), 2)
_compra3, _ = preco_arroba(date(2023, 3, 1))
_preco3 = round((_touro3_peso / ARROBA_KG) * _compra3, 2)
cur.execute(
    "INSERT INTO animais (brinco, sexo, raca, data_compra, data_nascimento, preco_compra, user_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
    ('TOU-03', 'M', 'Angus', date(2023, 3, 1), date(2023, 3, 1), _preco3, uid)
)
touro_pool.append({'id': cur.lastrowid, 'brinco': 'TOU-03', 'ativo': True, 'entrada': date(2023, 3, 1)})
conn.commit()
registrar_caixa(date(2023, 3, 1), -_preco3)

pesagens_rows = []
for brinco, aid in matriz_id_by_brinco.items():
    peso0 = next(p for b, s, r, dc, _, p, u in matriz_rows if b == brinco)
    # preco_compra guardado como preço; peso real de entrada recomputado a partir do preço/compra
    pesagens_rows.append((aid, START, round(random.gauss(450, 20), 2)))
for brinco, aid in touro_id_by_brinco.items():
    pesagens_rows.append((aid, START, round(random.gauss(560, 25), 2)))
pesagens_rows.append((touro_pool[-1]['id'], date(2023, 3, 1), _touro3_peso))

matriz_pool = []
for brinco, aid in matriz_id_by_brinco.items():
    matriz_pool.append({'id': aid, 'brinco': brinco, 'ativa': True, 'elegivel_desde': START,
                         'entrada': START})

print(f"     {len(matriz_pool)} matrizes + {len(touro_pool)} touros fundadores")

# ══════════════════════════════════════════════════════════════════
# [6/12] PIPELINE COMERCIAL — compra/venda de lotes de 20 cabeças
# ══════════════════════════════════════════════════════════════════
print("[6/12] Simulando pipeline comercial (carência + regime estável)...")

custos_rows = []
medicacoes_rows = []
lote_seq = 0
wip = []  # fila FIFO de lotes comprados e ainda não vendidos
all_feeder_animais = []  # dicts para a passada de mortalidade
sales_log = []  # (data, cabecas) para o resumo final


def criar_lote_comercial(data_compra, boosted=False):
    global lote_seq
    lote_seq += 1
    codigo = f"REP-{lote_seq:03d}"
    compra_arroba, _ = preco_arroba(data_compra)
    pesos = [round(random.uniform(9.5, 10.0) if boosted else random.uniform(8.0, 10.0), 2) * ARROBA_KG
             for _ in range(LOTE_SIZE)]
    precos = [round((p / ARROBA_KG) * compra_arroba, 2) for p in pesos]
    custo_medio = round(sum(precos) / len(precos), 2)

    cur.execute(
        "INSERT INTO lotes (user_id, codigo_lote, descricao, data_aquisicao, custo_medio_cabeca) "
        "VALUES (%s, %s, %s, %s, %s)",
        (uid, codigo, 'Reposição - lote fundador' if boosted else 'Reposição para engorda',
         data_compra, custo_medio)
    )
    lote_id = cur.lastrowid

    rows = [(f"{codigo}-{i + 1:02d}", 'M', raca(), data_compra, precos[i], uid, lote_id)
            for i in range(LOTE_SIZE)]
    cur.executemany(
        "INSERT INTO animais (brinco, sexo, raca, data_compra, preco_compra, user_id, lote_id) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)", rows
    )
    conn.commit()
    cur.execute("SELECT id FROM animais WHERE lote_id = %s ORDER BY id", (lote_id,))
    ids = [r[0] for r in cur.fetchall()]

    for aid, peso in zip(ids, pesos):
        pesagens_rows.append((aid, data_compra, peso))
    for preco in precos:
        registrar_caixa(data_compra, -preco)

    animais_lote = [{'id': aid, 'peso_compra': peso, 'data_compra': data_compra, 'vivo': True}
                     for aid, peso in zip(ids, pesos)]
    all_feeder_animais.extend(animais_lote)
    return {'lote_id': lote_id, 'codigo': codigo, 'data_compra': data_compra, 'animais': animais_lote}


def vender_lote(cohort, data_venda):
    _, venda_arroba = preco_arroba(data_venda)
    updates = []
    for a in cohort['animais']:
        if not a['vivo']:
            continue
        peso_venda = round(random.uniform(20.0, 22.0), 2) * ARROBA_KG
        preco_venda = round((peso_venda / ARROBA_KG) * venda_arroba, 2)
        updates.append((data_venda, preco_venda, a['id']))
        pesagens_rows.append((a['id'], data_venda, peso_venda))
        registrar_caixa(data_venda, preco_venda)
    if updates:
        cur.executemany("UPDATE animais SET data_venda=%s, preco_venda=%s WHERE id=%s", updates)
        conn.commit()
    sales_log.append((data_venda, len(updates)))
    return len(updates)


# --- Fase 1: carência (cadência lenta, sem vendas) ---
FOUNDER_GMD_ALVO = 0.90
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

print(f"     Carência: {len(wip)} lotes comprados até a 1ª venda "
      f"({dias_ate_20arroba} dias / {dias_ate_20arroba / 30.4:.1f} meses)")

vender_lote(wip.pop(0), data_primeira_venda)
data_ultima_venda = data_primeira_venda

# --- Fase 2: regime estável (venda ~36 dias, compra 5-7 dias após, ramp-up de WIP) ---
ramp_ate = data_primeira_venda + timedelta(days=548)  # ~18 meses de ramp-up de WIP
while data_ultima_venda < END:
    proxima_venda = data_ultima_venda + timedelta(days=random.randint(34, 39))
    if proxima_venda > END:
        break

    data_compra_reposicao = data_ultima_venda + timedelta(days=random.randint(5, 7))
    wip.append(criar_lote_comercial(data_compra_reposicao))

    if len(wip) < TARGET_WIP and proxima_venda <= ramp_ate:
        data_extra = data_compra_reposicao + timedelta(days=random.randint(10, 16))
        if data_extra < END:
            wip.append(criar_lote_comercial(data_extra))

    if wip:
        vender_lote(wip.pop(0), proxima_venda)
    data_ultima_venda = proxima_venda

lotes_restantes_ativos = wip  # seguem ativos em 30/06/2026 (natural — meio de ciclo)
print(f"     {lote_seq} lotes comerciais comprados, {len(sales_log)} vendas realizadas, "
      f"{len(lotes_restantes_ativos)} lotes ainda em curral no fim da simulação")

# ══════════════════════════════════════════════════════════════════
# [7/12] REPRODUÇÃO — coberturas, partos, crescimento da fazenda
# ══════════════════════════════════════════════════════════════════
print("[7/12] Simulando reprodução e nascimentos na fazenda...")

reproducao_rows = []
born_seq = 0
_counter = 0
pending = []  # heap (data, counter, ref_dict)


def touro_disponivel(d):
    disponiveis = [t for t in touro_pool if t.get('entrada', START) <= d]
    return random.choice(disponiveis) if disponiveis else None


for cow in matriz_pool:
    _counter += 1
    heapq.heappush(pending, (cow['elegivel_desde'], _counter, cow))

novilha_venda_pool = []  # animais individuais (crias) com sua própria data/objetivo de venda
boi_cria_pool = []

while pending:
    d, _, cow = heapq.heappop(pending)
    if d > END or not cow.get('ativa', True):
        continue

    touro_externo_txt = None
    touro = touro_disponivel(d)
    touro_id = touro['id'] if touro and random.random() > 0.15 else None
    if touro_id is None:
        touro_externo_txt = 'Central de IA - Sêmen Externo'

    roll = random.random()
    if roll < 0.82:
        resultado = 'vivo'
    elif roll < 0.90:
        resultado = 'aborto'
    else:
        resultado = 'natimorto'

    data_parto = d + timedelta(days=random.randint(278, 292)) if resultado in ('vivo', 'natimorto') else None
    reproducao_rows.append((uid, cow['id'], touro_id, touro_externo_txt, d, data_parto, resultado))

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
        pesagens_rows.append((calf_id, data_parto, peso_nasc))
        calf = {'id': calf_id, 'brinco': brinco, 'sexo': sexo, 'nascimento': data_parto,
                'peso_nasc': peso_nasc, 'vivo': True}

        if sexo == 'F' and random.random() < 0.55:
            calf['ativa'] = True
            calf['elegivel_desde'] = data_parto + timedelta(days=730)
            calf['entrada'] = data_parto
            _counter += 1
            heapq.heappush(pending, (calf['elegivel_desde'], _counter, calf))
            matriz_pool.append(calf)
        else:
            gmd_cria = round(clamp(random.gauss(0.72, 0.06), 0.55, 0.90), 3)
            alvo_kg = round(random.uniform(20.0, 22.0), 2) * ARROBA_KG
            dias_cria = int((alvo_kg - peso_nasc) / gmd_cria)
            data_venda_cria = data_parto + timedelta(days=dias_cria)
            entry = boi_cria_pool if sexo == 'M' else novilha_venda_pool
            entry.append({'id': calf_id, 'peso_nasc': peso_nasc, 'nascimento': data_parto,
                           'data_venda_prevista': data_venda_cria, 'alvo_kg': alvo_kg, 'vivo': True})

    if d <= END:
        proximo = d + timedelta(days=random.randint(355, 395))
        if proximo <= END and cow.get('ativa', True):
            _counter += 1
            heapq.heappush(pending, (proximo, _counter, cow))

print(f"     {len(reproducao_rows)} coberturas, {born_seq} nascimentos na fazenda "
      f"({len(matriz_pool) - 10} novilhas incorporadas como futuras matrizes)")

# vende crias (bois e novilhas de descarte) individualmente ao atingir peso-alvo
for pool in (boi_cria_pool, novilha_venda_pool):
    for cria in pool:
        if cria['data_venda_prevista'] > END:
            continue
        _, venda_arroba = preco_arroba(cria['data_venda_prevista'])
        preco_venda = round((cria['alvo_kg'] / ARROBA_KG) * venda_arroba, 2)
        cur.execute("UPDATE animais SET data_venda=%s, preco_venda=%s WHERE id=%s",
                    (cria['data_venda_prevista'], preco_venda, cria['id']))
        pesagens_rows.append((cria['id'], cria['data_venda_prevista'], cria['alvo_kg']))
        registrar_caixa(cria['data_venda_prevista'], preco_venda)
        cria['vivo'] = True
conn.commit()

# ══════════════════════════════════════════════════════════════════
# [8/12] MORTALIDADE — 2% ao ano sobre o rebanho ativo
# ══════════════════════════════════════════════════════════════════
print("[8/12] Aplicando mortalidade natural (2% ao ano)...")

todos_animais = []  # (id, entrada, saida_planejada_ou_None) para checagem de mortalidade
for a in all_feeder_animais:
    todos_animais.append(a['id'])
for cow in matriz_pool:
    todos_animais.append(cow['id'])
for t in touro_pool:
    todos_animais.append(t['id'])
for pool in (boi_cria_pool, novilha_venda_pool):
    for c in pool:
        todos_animais.append(c['id'])

cur.execute(
    "SELECT id, data_compra, data_nascimento, data_venda FROM animais WHERE user_id = %s", (uid,)
)
snapshot = {r[0]: r for r in cur.fetchall()}

entry_peso_by_id = {}
for aid, d0, peso0 in pesagens_rows:
    if aid not in entry_peso_by_id or d0 < entry_peso_by_id[aid][0]:
        entry_peso_by_id[aid] = (d0, peso0)

obito_updates = []
custos_perda = []
for aid in todos_animais:
    row = snapshot.get(aid)
    if not row:
        continue
    _, dc, dn, dv = row
    if dv is not None:
        continue  # já tem destino definido (vendido) — mortalidade não se aplica
    entrada = dc or dn
    if not entrada or entrada >= END:
        continue
    ano_checagem = date(entrada.year, 12, 31)
    while ano_checagem < END:
        if ano_checagem >= entrada and random.random() < 0.02:
            morte_min = max(entrada, date(ano_checagem.year, 1, 1))
            morte_max = min(END, ano_checagem)
            if morte_max > morte_min:
                data_obito = rdate(morte_min, morte_max)
                causa = random.choice(MORTE_CAUSAS)
                obito_updates.append((data_obito, 0.00, aid))
                custos_perda.append((uid, 'Perda', 'Mortalidade', 0.00, data_obito,
                                      f'Óbito animal id={aid} - Causa: {causa}'))
                _, peso_entrada = entry_peso_by_id.get(aid, (entrada, 30.0))
                gmd_ate_morte = round(clamp(random.gauss(0.55, 0.15), 0.10, 0.90), 3)
                peso_obito = round(clamp(peso_entrada + gmd_ate_morte * (data_obito - entrada).days,
                                          peso_entrada, 750.0), 2)
                pesagens_rows.append((aid, data_obito, peso_obito))
                break
        ano_checagem = date(ano_checagem.year + 1, 12, 31)

if obito_updates:
    cur.executemany("UPDATE animais SET data_venda=%s, preco_venda=%s WHERE id=%s AND data_venda IS NULL",
                     obito_updates)
    conn.commit()
custos_rows.extend(custos_perda)
print(f"     {len(obito_updates)} óbitos registrados sobre {len(todos_animais)} animais no rebanho")

# ══════════════════════════════════════════════════════════════════
# [9/12] PESAGENS — animais ainda ativos em 30/06/2026 (com outliers de GMD)
# ══════════════════════════════════════════════════════════════════
print("[9/12] Gerando pesagens de acompanhamento para animais ativos...")

cur.execute(
    "SELECT id, data_compra, data_nascimento FROM animais "
    "WHERE user_id = %s AND data_venda IS NULL AND deleted_at IS NULL", (uid,)
)
ativos = cur.fetchall()
random.shuffle(ativos)
n_ativos = len(ativos)
n_ruim = max(1, round(n_ativos * 0.05))
n_exc = max(1, round(n_ativos * 0.05))

for idx, (aid, dc, dn) in enumerate(ativos):
    entrada = dc or dn
    if not entrada or entrada >= END:
        continue
    dias = (END - entrada).days
    if idx < n_ruim:
        gmd = gmd_ruim()
    elif idx < n_ruim + n_exc:
        gmd = gmd_excecional()
    else:
        gmd = gmd_normal()
    entrada_reg, peso_base = entry_peso_by_id.get(aid, (entrada, 33.0 if dn and not dc else 270.0))
    peso_atual = round(clamp(peso_base + gmd * dias, peso_base, 750.0), 2)
    pesagens_rows.append((aid, END, peso_atual))
    if dias > 150:
        meio_data = entrada + timedelta(days=dias // 2)
        pesagens_rows.append((aid, meio_data, round(clamp(peso_base + gmd * (dias // 2), peso_base, 750.0), 2)))

print(f"     {n_ativos} animais ativos ({n_ruim} outliers 'ruim', {n_exc} outliers 'excecional')")

# ══════════════════════════════════════════════════════════════════
# [10/12] MEDICAÇÕES — febre aftosa anual + anabólico trimestral (machos)
# ══════════════════════════════════════════════════════════════════
print("[10/12] Gerando medicações (aftosa + anabólico)...")

cur.execute(
    "SELECT id, sexo, data_compra, data_nascimento, data_venda FROM animais WHERE user_id = %s", (uid,)
)
todos = cur.fetchall()

aftosa_por_data = {}
anab_por_data = {}
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

for dt, qtd in aftosa_por_data.items():
    mov(p_aftosa, 'entrada', qtd, 1.20, dt - timedelta(days=5), 'Compra para aplicação anual')
    mov(p_aftosa, 'saida', qtd, None, dt, 'Vacinação do rebanho')
for dt, qtd in anab_por_data.items():
    mov(p_anab, 'entrada', qtd, 2.00, dt - timedelta(days=5), 'Compra para aplicação trimestral')
    mov(p_anab, 'saida', qtd, None, dt, 'Aplicação em machos ativos')

print(f"     {len(medicacoes_rows)} medicações programadas")

# ══════════════════════════════════════════════════════════════════
# [11/12] FOLHA DE PAGAMENTO
# ══════════════════════════════════════════════════════════════════
print("[11/12] Lançando folha de pagamento mensal...")

d = date(START.year, START.month, 5)
while d <= END:
    custos_rows.append((uid, 'Fixo', 'Salário', VAQUEIRO_SALARIO, d, 'Salário mensal - Vaqueiro'))
    custos_rows.append((uid, 'Fixo', 'Salário', float(SALARIO_MINIMO[d.year]), d,
                         'Salário mensal - Cerqueiro (salário mínimo vigente)'))
    registrar_caixa(d, -(VAQUEIRO_SALARIO + SALARIO_MINIMO[d.year]))
    d = (d.replace(day=1) + timedelta(days=32)).replace(day=5)

print(f"     {len(custos_rows)} lançamentos de custos operacionais no total")

# ══════════════════════════════════════════════════════════════════
# [12/12] OCUPAÇÕES — snapshot de alocação em pasto (situação atual)
# ══════════════════════════════════════════════════════════════════
print("[12/12] Alocando rebanho ativo nos pastos (snapshot atual)...")

cur.execute(
    "SELECT id, sexo FROM animais WHERE user_id = %s AND data_venda IS NULL AND deleted_at IS NULL", (uid,)
)
ativos_final = cur.fetchall()
machos_ativos = [aid for aid, sexo in ativos_final if sexo == 'M']
femeas_ativas = [aid for aid, sexo in ativos_final if sexo == 'F']
random.shuffle(machos_ativos)

DATA_ENTRADA = END - timedelta(days=45)
grupos_machos = [machos_ativos[i::4] for i in range(4)]  # 4 piquetes de engorda
alocacoes = list(zip(modulos[:4], grupos_machos)) + [(modulos[5], femeas_ativas)] if len(modulos) > 5 else []

for modulo_id, ids in alocacoes:
    if not ids:
        continue
    cur.execute("INSERT INTO ocupacoes (modulo_id, user_id, data_entrada) VALUES (%s, %s, %s)",
                (modulo_id, uid, DATA_ENTRADA))
    occ_id = cur.lastrowid
    cur.executemany("INSERT INTO ocupacao_animais (ocupacao_id, animal_id) VALUES (%s, %s)",
                     [(occ_id, aid) for aid in ids])
conn.commit()

# ══════════════════════════════════════════════════════════════════
# BULK INSERT — pesagens, medicações, custos, reprodução, estoque
# ══════════════════════════════════════════════════════════════════
print("\nGravando registros em lote...")
bulk("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", pesagens_rows)
print(f"     {len(pesagens_rows)} pesagens")
bulk("INSERT INTO medicacoes (animal_id, data_aplicacao, nome_medicamento, custo, observacoes) "
     "VALUES (%s, %s, %s, %s, %s)", medicacoes_rows)
print(f"     {len(medicacoes_rows)} medicações")
bulk("INSERT INTO custos_operacionais (user_id, categoria, tipo_custo, valor, data_custo, descricao) "
     "VALUES (%s, %s, %s, %s, %s, %s)", custos_rows)
print(f"     {len(custos_rows)} custos operacionais")
bulk("INSERT INTO reproducao (user_id, vaca_id, touro_id, touro_externo, data_cobertura, data_parto, resultado) "
     "VALUES (%s, %s, %s, %s, %s, %s, %s)", reproducao_rows)
print(f"     {len(reproducao_rows)} registros de reprodução")
bulk("INSERT INTO estoque_movimentacoes (user_id, produto_id, tipo, quantidade, custo_unitario, motivo, data_mov) "
     "VALUES (%s, %s, %s, %s, %s, %s, %s)", estoque_mov_rows)
print(f"     {len(estoque_mov_rows)} movimentações de estoque")

# ══════════════════════════════════════════════════════════════════
# RESUMO E VALIDAÇÃO DE CAIXA
# ══════════════════════════════════════════════════════════════════
caixa_ledger.sort(key=lambda x: x[0])
saldo = 0.0
saldo_minimo = 0.0
data_minimo = START
saldo_por_ano = {}
for d, v in caixa_ledger:
    saldo += v
    if saldo < saldo_minimo:
        saldo_minimo = saldo
        data_minimo = d
    saldo_por_ano[d.year] = saldo

cur.execute("SELECT COUNT(*) FROM animais WHERE user_id=%s AND data_venda IS NULL AND deleted_at IS NULL", (uid,))
n_ativos_f = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM animais WHERE user_id=%s AND sexo='M' AND data_venda IS NULL AND deleted_at IS NULL", (uid,))
n_machos_f = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM animais WHERE user_id=%s AND sexo='F' AND data_venda IS NULL AND deleted_at IS NULL", (uid,))
n_femeas_f = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM animais WHERE user_id=%s AND data_venda IS NOT NULL", (uid,))
n_vendidos_f = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM animais WHERE user_id=%s AND data_nascimento IS NOT NULL", (uid,))
n_nascidos_f = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM animais WHERE user_id=%s", (uid,))
n_total_f = cur.fetchone()[0]

print(f"""
╔════════════════════════════════════════════════════════════════╗
║  Conta demonstracao — histórico 2020-01-01 a 2026-06-30         ║
╠════════════════════════════════════════════════════════════════╣
║  Rebanho ativo hoje : {n_ativos_f:<5}  (M {n_machos_f} / F {n_femeas_f} = """
      f"""{100*n_femeas_f/max(1,n_ativos_f):.1f}% fêmeas)
║  Total já vendido   : {n_vendidos_f:<5}
║  Total já cadastrado: {n_total_f:<5}
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

conn.close()
print("Concluído.")
