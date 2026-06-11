#!/usr/bin/env python3
"""
Seed: conta demonstracao — Fazenda São Marcos (pitch)
  Usuário : demonstracao
  Senha   : demonstracao
  Período : 2022 → 2026

Roda localmente ou no Railway:
    railway run python seed_demo.py
"""
import os, random
from datetime import date, timedelta
from dotenv import load_dotenv
import mysql.connector
from werkzeug.security import generate_password_hash

load_dotenv()
random.seed(99)

TODAY = date(2026, 6, 10)
START = date(2022, 3, 1)

conn = mysql.connector.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME'),
    port=int(os.getenv('DB_PORT', 3306)),
    autocommit=False,
)
cur = conn.cursor()

# ── helpers ─────────────────────────────────────────────────────
def rdate(s, e):
    return s + timedelta(days=random.randint(0, max(0, (e - s).days)))

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def rand_gmd(cat='norm'):
    if cat == 'up':
        return round(clamp(random.gauss(1.10, 0.06), 0.95, 1.30), 3)
    if cat == 'dn':
        return round(clamp(random.gauss(0.38, 0.07), 0.20, 0.50), 3)
    return round(clamp(random.gauss(0.780, 0.060), 0.620, 0.960), 3)

def gmd_cats(n):
    n_dn = max(1, round(n * 0.05))
    n_up = max(1, round(n * 0.05))
    cats = ['dn'] * n_dn + ['up'] * n_up + ['norm'] * (n - n_dn - n_up)
    random.shuffle(cats)
    return cats

def bulk(sql, rows, chunk=500):
    for i in range(0, len(rows), chunk):
        cur.executemany(sql, rows[i:i+chunk])
    conn.commit()

ARROBA_COMPRA = {2022: 235, 2023: 248, 2024: 262, 2025: 275, 2026: 290}
ARROBA_VENDA  = {2022: 280, 2023: 295, 2024: 310, 2025: 325, 2026: 345}

def pc(data, peso): return round((peso / 30) * ARROBA_COMPRA.get(data.year, 260), 2)
def pv(data, peso): return round((peso / 30) * ARROBA_VENDA.get(data.year, 310), 2)

def pesagens_para(aid, dc, last_date, ini, gmd):
    rows, d, w = [], dc, round(ini, 2)
    while d <= last_date:
        rows.append((aid, d, round(w, 2)))
        d += timedelta(days=90)
        w = clamp(w + gmd * 90, ini, 800)
    if rows and rows[-1][1] < last_date:
        extra = (last_date - rows[-1][1]).days
        rows.append((aid, last_date, round(clamp(rows[-1][2] + gmd * extra, ini, 800), 2)))
    return rows if len(rows) >= 2 else []

# ══════════════════════════════════════════════════════════════
# 1. USUÁRIO
# ══════════════════════════════════════════════════════════════
print("[1/8] Usuário...")
USERNAME, SENHA = 'demonstracao', 'demonstracao'

cur.execute("SELECT id FROM usuarios WHERE LOWER(username)=LOWER(%s)", (USERNAME,))
row = cur.fetchone()
if row:
    uid = row[0]
    print(f"     uid={uid} — limpando dados...")
    cur.execute("SELECT id FROM animais WHERE user_id=%s", (uid,))
    aids = [r[0] for r in cur.fetchall()]
    if aids:
        ph = ','.join(['%s'] * len(aids))
        cur.execute(f"DELETE FROM reproducao WHERE vaca_id IN ({ph})", aids)
        cur.execute(f"DELETE FROM pesagens WHERE animal_id IN ({ph})", aids)
        cur.execute(f"DELETE FROM medicacoes WHERE animal_id IN ({ph})", aids)
        cur.execute("SELECT id FROM modulos WHERE user_id=%s", (uid,))
        mids = [r[0] for r in cur.fetchall()]
        if mids:
            pm = ','.join(['%s'] * len(mids))
            cur.execute(f"SELECT id FROM ocupacoes WHERE modulo_id IN ({pm})", mids)
            oids = [r[0] for r in cur.fetchall()]
            if oids:
                po = ','.join(['%s'] * len(oids))
                cur.execute(f"DELETE FROM ocupacao_animais WHERE ocupacao_id IN ({po})", oids)
                cur.execute(f"DELETE FROM ocupacoes WHERE id IN ({po})", oids)
            cur.execute(f"DELETE FROM modulos WHERE id IN ({pm})", mids)
        cur.execute("DELETE FROM pastos WHERE user_id=%s", (uid,))
        cur.execute(f"DELETE FROM animais WHERE id IN ({ph})", aids)
    cur.execute("DELETE FROM custos_operacionais WHERE user_id=%s", (uid,))
    cur.execute("DELETE FROM financial_schedule WHERE user_id=%s", (uid,))
    cur.execute("DELETE FROM estoque_movimentacoes WHERE user_id=%s", (uid,))
    cur.execute("DELETE FROM estoque_produtos WHERE user_id=%s", (uid,))
    cur.execute("DELETE FROM configuracoes WHERE user_id=%s", (uid,))
    cur.execute("UPDATE usuarios SET username=%s,password_hash=%s,email=%s WHERE id=%s",
                (USERNAME, generate_password_hash(SENHA), 'demo@fazendasaomarcos.com.br', uid))
    conn.commit()
else:
    cur.execute("INSERT INTO usuarios (username,password_hash,email) VALUES (%s,%s,%s)",
                (USERNAME, generate_password_hash(SENHA), 'demo@fazendasaomarcos.com.br'))
    uid = cur.lastrowid
    conn.commit()

cur.execute("INSERT INTO configuracoes (user_id,nome_fazenda,cidade_estado,area_total) VALUES (%s,%s,%s,%s)",
            (uid, 'Fazenda São Marcos', 'Araçatuba - SP', 420.0))
conn.commit()
print(f"     uid={uid}")

# ══════════════════════════════════════════════════════════════
# 2. ANIMAIS — coleta tudo em memória, insere em lote
# ══════════════════════════════════════════════════════════════
print("[2/8] Gerando animais (fêmeas, touros, bezerros, lotes)...")

animal_rows = []   # (brinco, sexo, dc, pc, dv, pv, user_id, mae_id, pai_id)
# Depois do INSERT coletamos IDs e montamos pesagens/medicações/reprodução

def a(brinco, sexo, dc, preco_c, dv=None, preco_v=None, mae_id=None, pai_id=None):
    animal_rows.append((brinco, sexo, dc, preco_c, dv, preco_v, uid, mae_id, pai_id))

# ── Matrizes (20 fêmeas) ──────────────────────────────────────
cow_meta = []   # (idx_in_animal_rows, dc, p_ini, gmd)
fgmds = gmd_cats(20)
for i in range(20):
    dc = rdate(date(2022, 3, 1), date(2022, 8, 31))
    p_ini = round(random.gauss(215, 15), 2)
    gmd_f = rand_gmd(fgmds[i]) * 0.70
    cow_meta.append((len(animal_rows), dc, p_ini, gmd_f))
    a(f"MAT{i+1:03d}", 'F', dc, pc(dc, p_ini))

# ── Touros (3) ────────────────────────────────────────────────
touro_meta = []
for nome, dc_t, peso_t in [('NEL001', date(2022, 3, 15), 520),
                            ('NEL002', date(2023, 6,  1), 545),
                            ('NEL003', date(2025, 1, 10), 560)]:
    touro_meta.append((len(animal_rows), dc_t, peso_t))
    a(nome, 'M', dc_t, pc(dc_t, peso_t))

# ── Lotes vendidos ────────────────────────────────────────────
sold_meta = []   # (idx, dc, dv, p_ini, gmd)

def lote_vendido(prefixo, n, dc_ini, dc_fim, p_media, gmds, dv_dias_min, dv_dias_max):
    for i in range(n):
        dc = rdate(dc_ini, dc_fim)
        p_ini = round(random.gauss(p_media, 17), 2)
        gmd = rand_gmd(gmds[i])
        dv = dc + timedelta(days=random.randint(dv_dias_min, dv_dias_max))
        dv = min(dv, TODAY - timedelta(days=5))
        p_fim = clamp(p_ini + gmd * (dv - dc).days, 440, 610)
        sold_meta.append((len(animal_rows), dc, dv, p_ini, gmd))
        a(f"{prefixo}-{i+1:03d}", 'M', dc, pc(dc, p_ini), dv, pv(dv, p_fim))

lote_vendido('L22', 40, date(2022, 3, 1), date(2022, 5, 31), 242, gmd_cats(40), 390, 430)
lote_vendido('L23', 60, date(2023, 2, 1), date(2023, 5, 31), 248, gmd_cats(60), 380, 420)
lote_vendido('L24', 80, date(2024, 1, 15), date(2024, 6, 30), 252, gmd_cats(80), 360, 420)
lote_vendido('L25', 100, date(2025, 2, 1), date(2025, 8, 31), 258, gmd_cats(100), 310, 390)

# ── Lotes ativos (no pasto) ───────────────────────────────────
active_meta = []  # (idx, dc, p_ini, gmd)

def lote_ativo(prefixo, n, dc_ini, dc_fim, p_media, gmds):
    for i in range(n):
        dc = rdate(dc_ini, dc_fim)
        p_ini = round(random.gauss(p_media, 17), 2)
        gmd = rand_gmd(gmds[i])
        active_meta.append((len(animal_rows), dc, p_ini, gmd))
        a(f"{prefixo}-{i+1:03d}", 'M', dc, pc(dc, p_ini))

lote_ativo('L26',  60, date(2026, 1, 10), date(2026, 4, 30), 262, gmd_cats(60))

# ══════════════════════════════════════════════════════════════
# INSERT ANIMAIS em lote
# ══════════════════════════════════════════════════════════════
bulk(
    "INSERT INTO animais (brinco,sexo,data_compra,preco_compra,data_venda,preco_venda,user_id,mae_id,pai_id) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
    animal_rows
)

# Recupera os IDs gerados (autoincrement sequencial)
cur.execute("SELECT id FROM animais WHERE user_id=%s ORDER BY id", (uid,))
all_ids = [r[0] for r in cur.fetchall()]

cow_ids    = [(all_ids[idx], dc, p_ini) for idx, dc, p_ini, _ in cow_meta]
touro_ids  = [(all_ids[idx], dc_t) for idx, dc_t, _ in touro_meta]
sold_ids   = [(all_ids[idx], dc, dv, p_ini, gmd) for idx, dc, dv, p_ini, gmd in sold_meta]
active_ids = [(all_ids[idx], dc, p_ini, gmd) for idx, dc, p_ini, gmd in active_meta]

print(f"     {len(all_ids)} animais inseridos "
      f"({len(cow_ids)} F + {len(touro_ids)} touros + {len(sold_ids)} vendidos + {len(active_ids)} ativos)")

# ══════════════════════════════════════════════════════════════
# 3. BEZERROS (INSERT + REPRODUÇÃO)
# ══════════════════════════════════════════════════════════════
print("[3/8] Bezerros nascidos na fazenda...")

bezerro_rows = []
repro_rows   = []
bz_meta      = []  # (idx_em_bezerro_rows, birth, p_ini, gmd)
bgmds = gmd_cats(52)

for i in range(52):
    mae_id, mae_dc, _ = random.choice(cow_ids)
    touro_id = random.choice(touro_ids)[0]
    earliest = max(date(2022, 9, 1), mae_dc + timedelta(days=300))
    latest   = date(2025, 11, 30)
    if earliest > latest:
        continue
    birth = rdate(earliest, latest)
    sexo  = 'M' if random.random() < 0.55 else 'F'
    p_ini = round(random.gauss(36 if sexo == 'M' else 33, 4), 2)
    gmd   = rand_gmd(bgmds[i])
    bz_meta.append((len(bezerro_rows), birth, p_ini, gmd))
    bezerro_rows.append((f"NZ{i+1:03d}", sexo, birth, 0.00, None, None, uid, mae_id, touro_id))
    cob = birth - timedelta(days=random.randint(270, 285))
    repro_rows.append((uid, mae_id, touro_id, cob, birth, 'vivo'))

bulk("INSERT INTO animais (brinco,sexo,data_compra,preco_compra,data_venda,preco_venda,user_id,mae_id,pai_id) "
     "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", bezerro_rows)

cur.execute("SELECT id FROM animais WHERE user_id=%s AND brinco LIKE 'NZ%' ORDER BY id", (uid,))
bz_ids = [r[0] for r in cur.fetchall()]
born_ids = [(bz_ids[idx], birth) for idx, birth, _, _ in bz_meta]

bulk("INSERT INTO reproducao (user_id,vaca_id,touro_id,data_cobertura,data_parto,resultado) "
     "VALUES (%s,%s,%s,%s,%s,%s)", repro_rows)

print(f"     {len(born_ids)} bezerros + {len(repro_rows)} registros reprodução")

# ══════════════════════════════════════════════════════════════
# 4. PESAGENS (bulk)
# ══════════════════════════════════════════════════════════════
print("[4/8] Pesagens...")

all_pesagens = []

# Fêmeas
for (aid, dc, p_ini), (_, _, _, gmd) in zip(cow_ids, cow_meta):
    all_pesagens += pesagens_para(aid, dc, TODAY, p_ini, gmd)

# Touros (pesagem só de controle, 2 pontos)
for (aid, dc_t), (_, _, peso_t) in zip(touro_ids, touro_meta):
    all_pesagens.append((aid, dc_t, peso_t))
    all_pesagens.append((aid, TODAY, round(clamp(peso_t + 0.3 * (TODAY - dc_t).days, peso_t, 800), 2)))

# Vendidos — entrada e saída (simples)
for aid, dc, dv, p_ini, gmd in sold_ids:
    p_fim = clamp(p_ini + gmd * (dv - dc).days, 440, 620)
    all_pesagens.append((aid, dc, round(p_ini, 2)))
    mid_d = dc + timedelta(days=(dv - dc).days // 2)
    all_pesagens.append((aid, mid_d, round(clamp(p_ini + gmd * (mid_d - dc).days, p_ini, 800), 2)))
    all_pesagens.append((aid, dv, round(p_fim, 2)))

# Bezerros
for (aid, birth), (_, _, p_ini, gmd) in zip(born_ids, bz_meta):
    all_pesagens += pesagens_para(aid, birth, TODAY, p_ini, gmd)

# Ativos
for aid, dc, p_ini, gmd in active_ids:
    all_pesagens += pesagens_para(aid, dc, TODAY, p_ini, gmd)

bulk("INSERT INTO pesagens (animal_id,data_pesagem,peso) VALUES (%s,%s,%s)", all_pesagens)
print(f"     {len(all_pesagens)} pesagens")

# ══════════════════════════════════════════════════════════════
# 5. MEDICAÇÕES (bulk)
# ══════════════════════════════════════════════════════════════
print("[5/8] Medicações...")

all_meds = []  # (animal_id, data, nome, custo)

def meds_para(aid, dc, last_date, nome, custo, intervalo):
    d = dc + timedelta(days=random.randint(5, 20))
    while d <= last_date:
        all_meds.append((aid, d, nome, custo))
        d += timedelta(days=intervalo + random.randint(-5, 5))

# Febre Aftosa (Mai e Nov) — todos os ativos
all_active_meds = (
    [(aid, dc) for aid, dc, _ in cow_ids] +
    [(aid, dc_t) for aid, dc_t in touro_ids] +
    [(aid, birth) for aid, birth in born_ids] +
    [(aid, dc) for aid, dc, _, _ in active_ids]
)
for aid, dc in all_active_meds:
    for ano in range(dc.year, TODAY.year + 1):
        for mes in (5, 11):
            dt = date(ano, mes, 15)
            if dc <= dt <= TODAY:
                all_meds.append((aid, dt, 'Febre Aftosa', 1.50))

# Anabólico trimestral — machos ativos e bezerros machos
for aid, dc, p_ini, gmd in active_ids:
    meds_para(aid, dc, TODAY, 'Anabólico', 1.70, 90)

# Aftosa vendidos + anabólico 1 dose inicial
for aid, dc, dv, _, _ in sold_ids:
    for ano in range(dc.year, dv.year + 1):
        for mes in (5, 11):
            dt = date(ano, mes, 15)
            if dc <= dt <= dv:
                all_meds.append((aid, dt, 'Febre Aftosa', 1.50))
    d1 = dc + timedelta(days=30)
    if d1 <= dv:
        all_meds.append((aid, d1, 'Anabólico', 1.70))
    d2 = dc + timedelta(days=120)
    if d2 <= dv:
        all_meds.append((aid, d2, 'Anabólico', 1.70))

bulk("INSERT INTO medicacoes (animal_id,data_aplicacao,nome_medicamento,custo) VALUES (%s,%s,%s,%s)", all_meds)
print(f"     {len(all_meds)} medicações")

# ══════════════════════════════════════════════════════════════
# 6. CUSTOS OPERACIONAIS
# ══════════════════════════════════════════════════════════════
print("[6/8] Custos operacionais...")

custos = []
d = START
while d <= TODAY.replace(day=1):
    ano = d.year
    arr = {2022: 5500, 2023: 6000, 2024: 6500, 2025: 7000, 2026: 7500}.get(ano, 7000)
    sal = {2022: 2200, 2023: 2400, 2024: 2600, 2025: 2800, 2026: 3000}.get(ano, 2800)
    custos += [
        (uid, 'Fixo',    'Arrendamento', arr,    d, 'Arrendamento mensal das pastagens'),
        (uid, 'Fixo',    'Salário',       sal,    d, 'Salário do vaqueiro'),
        (uid, 'Fixo',    'Salário',      1500.0,  d, 'Salário do auxiliar'),
        (uid, 'Variavel','Nutrição',      620.0,  d, 'Sal mineral e suplemento'),
        (uid, 'Variavel','Combustível',   420.0,  d, 'Gasolina e diesel'),
    ]
    d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)

d = START
while d <= TODAY:
    custos.append((uid, 'Variavel', 'Manutenção', 750.0, d, 'Manutenção de cercas e aguadas'))
    d += timedelta(days=91)

bulk("INSERT INTO custos_operacionais (user_id,categoria,tipo_custo,valor,data_custo,descricao) VALUES (%s,%s,%s,%s,%s,%s)", custos)
print(f"     {len(custos)} lançamentos")

# ══════════════════════════════════════════════════════════════
# 7. ESTOQUE VIRTUAL
# ══════════════════════════════════════════════════════════════
print("[7/8] Estoque...")

def produto(nome, unidade, categoria, minimo):
    cur.execute("INSERT INTO estoque_produtos (user_id,nome,unidade,categoria,estoque_minimo) VALUES (%s,%s,%s,%s,%s)",
                (uid, nome, unidade, categoria, minimo))
    conn.commit()
    return cur.lastrowid

def mov(pid, tipo, qtd, custo_unit, data, motivo):
    return (uid, pid, tipo, qtd, custo_unit, motivo, data)

movs = []

p_aftosa = produto('Vacina Febre Aftosa', 'dose', 'vacina', 50)
d = START
while d <= TODAY:
    movs.append(mov(p_aftosa, 'entrada', 120, 1.50, d, 'Compra semestral'))
    if d + timedelta(days=8) <= TODAY:
        movs.append(mov(p_aftosa, 'saida', 120, None, d + timedelta(days=8), 'Vacinação do rebanho'))
    d += timedelta(days=182)

p_anab = produto('Anabólico Bovino (cx 50 doses)', 'caixa', 'medicamento', 2)
d = START
while d <= TODAY:
    movs.append(mov(p_anab, 'entrada', 3, 170.00, d, 'Compra trimestral'))
    if d + timedelta(days=85) <= TODAY:
        movs.append(mov(p_anab, 'saida', 3, None, d + timedelta(days=85), 'Aplicação no rebanho'))
    d += timedelta(days=91)

p_iver = produto('Ivermectina 1% (frasco 500ml)', 'frasco', 'medicamento', 3)
d = START
while d <= TODAY:
    movs.append(mov(p_iver, 'entrada', 4, 65.00, d, 'Reposição trimestral'))
    if d + timedelta(days=6) <= TODAY:
        movs.append(mov(p_iver, 'saida', 4, None, d + timedelta(days=6), 'Controle de parasitas'))
    d += timedelta(days=91)

p_sal = produto('Sal Mineral (saco 30kg)', 'saco', 'mineral', 5)
for ano in range(2022, 2027):
    for mes in (1, 4, 7, 10):
        dt = date(ano, mes, 5)
        if dt <= TODAY:
            movs.append(mov(p_sal, 'entrada', 12, 78.00, dt, f'Compra trimestral {ano}'))
            if dt + timedelta(days=88) <= TODAY:
                movs.append(mov(p_sal, 'saida', 11, None, dt + timedelta(days=88), 'Consumo do rebanho'))

p_arame = produto('Arame Farpado (rolo 250m)', 'rolo', 'outro', 2)
for dt, qtd in [(date(2022, 3, 10), 5), (date(2023, 8, 15), 3), (date(2024, 11, 5), 4), (date(2025, 6, 20), 3)]:
    movs.append(mov(p_arame, 'entrada', qtd, 320.00, dt, 'Reforma de cercas'))
for dt, qtd in [(date(2022, 4, 1), 2), (date(2023, 9, 1), 2), (date(2024, 12, 1), 3)]:
    if dt <= TODAY:
        movs.append(mov(p_arame, 'saida', qtd, None, dt, 'Uso na manutenção'))

bulk("INSERT INTO estoque_movimentacoes (user_id,produto_id,tipo,quantidade,custo_unitario,motivo,data_mov) "
     "VALUES (%s,%s,%s,%s,%s,%s,%s)", movs)
print("     Estoque OK")

# ══════════════════════════════════════════════════════════════
# 8. PASTOS (10 piquetes + maternidade + recria)
# ══════════════════════════════════════════════════════════════
print("[8/8] Pastos...")

all_male_active = [aid for aid, _, _, _ in active_ids]
random.shuffle(all_male_active)
all_female = [aid for aid, _, _ in cow_ids]
all_born   = [aid for aid, _ in born_ids]

pasto_config = [
    ('Piquete Norte A',   'Brachiaria Brizantha',   35.0, 50, all_male_active[0:30]),
    ('Piquete Norte B',   'Brachiaria Brizantha',   35.0, 50, all_male_active[30:]),
    ('Piquete Sul A',     'Mombaça',                30.0, 45, []),
    ('Piquete Sul B',     'Mombaça',                30.0, 45, []),
    ('Piquete Centro A',  'Panicum Maximum',         28.0, 40, []),
    ('Piquete Centro B',  'Panicum Maximum',         28.0, 40, []),
    ('Pasto Matrizes',    'Brachiaria Ruziziensis',  22.0, 30, all_female),
    ('Pasto Recria',      'Brachiaria Decumbens',    18.0, 30, all_born),
    ('Piquete Reserva A', 'Brachiaria Brizantha',    30.0, 45, []),
    ('Piquete Reserva B', 'Mombaça',                 25.0, 40, []),
]

DATA_ENTRADA = TODAY - timedelta(days=55)
for nome, forrageira, area, cap, animais in pasto_config:
    cur.execute("INSERT INTO pastos (user_id,nome,area_hectares,forrageira,capacidade_ua) VALUES (%s,%s,%s,%s,%s)",
                (uid, nome, area, forrageira, cap))
    pasto_id = cur.lastrowid
    cur.execute("INSERT INTO modulos (pasto_id,user_id,nome,area_hectares,capacidade_ua) VALUES (%s,%s,%s,%s,%s)",
                (pasto_id, uid, f"Módulo {nome}", area, cap))
    modulo_id = cur.lastrowid
    if animais:
        cur.execute("INSERT INTO ocupacoes (modulo_id,user_id,data_entrada) VALUES (%s,%s,%s)",
                    (modulo_id, uid, DATA_ENTRADA))
        occ_id = cur.lastrowid
        cur.executemany("INSERT INTO ocupacao_animais (ocupacao_id,animal_id) VALUES (%s,%s)",
                        [(occ_id, aid) for aid in animais])
conn.commit()

# ══════════════════════════════════════════════════════════════
# RESUMO
# ══════════════════════════════════════════════════════════════
def count(sql, p=(uid,)):
    cur.execute(sql, p)
    return cur.fetchone()[0]

n_at = count("SELECT COUNT(*) FROM animais WHERE user_id=%s AND data_venda IS NULL AND deleted_at IS NULL")
n_vd = count("SELECT COUNT(*) FROM animais WHERE user_id=%s AND data_venda IS NOT NULL AND deleted_at IS NULL")
n_ps = count("SELECT COUNT(*) FROM pesagens p JOIN animais a ON p.animal_id=a.id WHERE a.user_id=%s")
n_md = count("SELECT COUNT(*) FROM medicacoes m JOIN animais a ON m.animal_id=a.id WHERE a.user_id=%s")
n_co = count("SELECT COUNT(*) FROM custos_operacionais WHERE user_id=%s")
n_pa = count("SELECT COUNT(*) FROM pastos WHERE user_id=%s")
n_ep = count("SELECT COUNT(*) FROM estoque_produtos WHERE user_id=%s")
n_rep= count("SELECT COUNT(*) FROM reproducao WHERE user_id=%s")

print(f"""
╔══════════════════════════════════════════════════╗
║  Conta demonstracao criada com sucesso!          ║
║  Usuário : demonstracao                          ║
║  Senha   : demonstracao                          ║
║  Fazenda : Fazenda São Marcos — Araçatuba SP     ║
║  Período : 2022 → 2026 (420 ha)                 ║
╠══════════════════════════════════════════════════╣
║  Ativos      : {n_at:<5}  Vendidos  : {n_vd:<5}              ║
║  Pesagens    : {n_ps:<5}  Medicações: {n_md:<5}              ║
║  Custos Op.  : {n_co:<5}  Pastos    : {n_pa:<5}              ║
║  Reprodução  : {n_rep:<5}  Produtos  : {n_ep:<5}              ║
╚══════════════════════════════════════════════════╝
""")
conn.close()
