#!/usr/bin/env python3
"""
Auditoria de QA do seed histórico da conta 'demonstracao' (seed_demo_historico.py).

Este projeto não usa SQLAlchemy/ORM (ver CLAUDE.md: "SQL puro — não introduzir SQLAlchemy
ou ORM") — não há `db = SQLAlchemy(app)` nem modelos declarativos em models.py (só um User
simples para o Flask-Login). Não existe, portanto, um app.app_context() com sessão ORM para
consultar. Este script usa a mesma conexão mysql.connector direta que o resto do projeto
(db_config.py / seed_demo_historico.py) para rodar as mesmas checagens pedidas, em SQL puro.

Roda cada checagem, imprime PASSOU/FALHOU com o valor medido, e no fim mostra um resumo.

Rodar:
    python scripts/auditoria_seed.py
"""
import os
from datetime import date, timedelta
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

END = date(2026, 6, 30)

conn = mysql.connector.connect(
    host=os.getenv('DB_HOST'), user=os.getenv('DB_USER'), password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME'), port=int(os.getenv('DB_PORT', 3306)),
)
cur = conn.cursor()

resultados = []  # (secao, nome, passou, detalhe)


def checa(secao, nome, passou, detalhe):
    resultados.append((secao, nome, passou, detalhe))
    status = "PASSOU" if passou else "FALHOU"
    print(f"  [{status}] {nome} — {detalhe}")


def q(sql, params=()):
    cur.execute(sql, params)
    return cur.fetchall()


cur.execute("SELECT id FROM usuarios WHERE LOWER(username) = LOWER(%s)", ('demonstracao',))
row = cur.fetchone()
if not row:
    raise SystemExit("Usuário 'demonstracao' não encontrado.")
uid = row[0]
print(f"Auditando conta demonstracao (uid={uid})\n")

# ══════════════════════════════════════════════════════════════════
# 1. VALIDAÇÃO FINANCEIRA E LUCRO
# ══════════════════════════════════════════════════════════════════
print("=== 1. Validação Financeira e Lucro ===")

aporte = q("SELECT valor, data_custo FROM custos_operacionais "
           "WHERE user_id=%s AND categoria='Aporte' AND data_custo='2020-01-01'", (uid,))
ok = len(aporte) == 1 and float(aporte[0][0]) == -600000.00
checa('financeiro', 'Aporte de Capital Inicial R$600.000,00 em Jan/2020', ok,
      f"encontrado(s)={len(aporte)}, valor={aporte[0][0] if aporte else 'n/a'}")

fluxo = {r[0]: r[1:] for r in q(
    "SELECT ano, total_entradas, total_compras, total_med, total_ops FROM v_fluxo_caixa "
    "WHERE user_id=%s AND ano BETWEEN 2021 AND 2025 ORDER BY ano", (uid,))}
for ano in range(2021, 2026):
    if ano not in fluxo:
        checa('financeiro', f'Margem de lucro {ano} > 30%', False, "sem dados em v_fluxo_caixa")
        continue
    receita, compras, med, ops = (float(x) for x in fluxo[ano])
    despesas = compras + med + ops
    lucro = receita - despesas
    margem = (lucro / receita * 100) if receita else 0
    checa('financeiro', f'Margem de lucro {ano} > 30%', margem > 30,
          f"receita=R${receita:,.2f}, despesas=R${despesas:,.2f}, lucro=R${lucro:,.2f}, margem={margem:.1f}%")

agio_compra = {r[0]: float(r[1]) for r in q(
    "SELECT YEAR(a.data_compra), AVG(a.preco_compra*30/p.peso) "
    "FROM animais a JOIN pesagens p ON p.animal_id=a.id AND p.data_pesagem=a.data_compra "
    "WHERE a.user_id=%s AND a.brinco LIKE 'REP-%%' GROUP BY YEAR(a.data_compra)", (uid,))}
agio_venda = {r[0]: float(r[1]) for r in q(
    "SELECT YEAR(a.data_venda), AVG(a.preco_venda*30/p.peso) "
    "FROM animais a JOIN pesagens p ON p.animal_id=a.id AND p.data_pesagem=a.data_venda "
    "WHERE a.user_id=%s AND a.brinco LIKE 'REP-%%' AND a.preco_venda>0 GROUP BY YEAR(a.data_venda)", (uid,))}
for ano in sorted(set(agio_compra) & set(agio_venda)):
    c, v = agio_compra[ano], agio_venda[ano]
    checa('financeiro', f'Regra do Ágio {ano} (compra > venda)', c > v,
          f"@compra=R${c:.2f}, @venda=R${v:.2f}, ágio médio=R${c - v:.2f}")

# ══════════════════════════════════════════════════════════════════
# 2. VALIDAÇÃO OPERACIONAL E GIRO
# ══════════════════════════════════════════════════════════════════
print("\n=== 2. Validação Operacional e Giro (~36 dias) ===")

vendas_ano = {r[0]: r[1] for r in q(
    "SELECT YEAR(data_venda), COUNT(*) FROM animais "
    "WHERE user_id=%s AND lote_id IS NOT NULL AND preco_venda>0 GROUP BY YEAR(data_venda)", (uid,))}
for ano in range(2021, 2026):
    n = vendas_ano.get(ano, 0)
    checa('giro', f'Cabeças vendidas em {ano} (~200/ano)', 150 <= n <= 260,
          f"{n} cabeças vendidas")

lotes_vendidos = q(
    "SELECT data_venda, COUNT(*) FROM animais "
    "WHERE user_id=%s AND lote_id IS NOT NULL AND preco_venda>0 GROUP BY data_venda ORDER BY data_venda", (uid,))
tam_venda_ok = sum(1 for _, n in lotes_vendidos if 16 <= n <= 20)
checa('giro', 'Lotes vendidos com ~20 cabeças (tolerância p/ mortalidade)',
      tam_venda_ok / max(1, len(lotes_vendidos)) > 0.85,
      f"{tam_venda_ok}/{len(lotes_vendidos)} lotes de venda com 16-20 cabeças")

lotes_comprados = q(
    "SELECT data_compra, COUNT(*) FROM animais "
    "WHERE user_id=%s AND lote_id IS NOT NULL GROUP BY data_compra ORDER BY data_compra", (uid,))
tam_compra_ok = sum(1 for _, n in lotes_comprados if n == 20)
checa('giro', 'Lotes comprados com exatamente 20 cabeças',
      tam_compra_ok == len(lotes_comprados),
      f"{tam_compra_ok}/{len(lotes_comprados)} lotes de compra com 20 cabeças")

datas_venda = sorted(r[0] for r in lotes_vendidos)
datas_compra = sorted(r[0] for r in lotes_comprados)
gaps_ok, gaps_total = 0, 0
for dv in datas_venda:
    posteriores = [dc for dc in datas_compra if dc > dv]
    if not posteriores:
        continue
    gap = (min(posteriores) - dv).days
    gaps_total += 1
    if 5 <= gap <= 7:
        gaps_ok += 1
checa('giro', 'Reposição ocorre 5-7 dias após venda',
      gaps_total > 0 and gaps_ok / gaps_total > 0.85,
      f"{gaps_ok}/{gaps_total} vendas seguidas de reposição em 5-7 dias")

# ══════════════════════════════════════════════════════════════════
# 3. ZOOTECNIA E REBANHO
# ══════════════════════════════════════════════════════════════════
print("\n=== 3. Zootecnia e Rebanho ===")

sexo_ativo = dict(q(
    "SELECT sexo, COUNT(*) FROM animais WHERE user_id=%s AND data_venda IS NULL AND deleted_at IS NULL "
    "GROUP BY sexo", (uid,)))
total_ativo = sum(sexo_ativo.values())
pct_f = sexo_ativo.get('F', 0) / max(1, total_ativo) * 100
checa('zootecnia', 'Rácio de gênero do rebanho ativo (~80M/20F)', 10 <= pct_f <= 30,
      f"M={sexo_ativo.get('M', 0)} ({100 - pct_f:.1f}%), F={sexo_ativo.get('F', 0)} ({pct_f:.1f}%)")

total_animais = q("SELECT COUNT(*) FROM animais WHERE user_id=%s", (uid,))[0][0]
nascidos_mae = q("SELECT COUNT(*) FROM animais WHERE user_id=%s AND mae_id IS NOT NULL", (uid,))[0][0]
nascidos_pai_e_mae = q(
    "SELECT COUNT(*) FROM animais WHERE user_id=%s AND pai_id IS NOT NULL AND mae_id IS NOT NULL", (uid,))[0][0]
pct_nascidos = nascidos_mae / max(1, total_animais) * 100
checa('zootecnia', 'Reprodução: ~20% nascidos na fazenda (mae_id preenchido)', 10 <= pct_nascidos <= 30,
      f"{nascidos_mae}/{total_animais} = {pct_nascidos:.1f}% com mae_id; "
      f"{nascidos_pai_e_mae} com pai_id E mae_id (15% dos partos usa sêmen externo → pai_id NULL por design)")

entrada = q(
    "SELECT p.peso FROM animais a JOIN pesagens p ON p.animal_id=a.id AND p.data_pesagem=a.data_compra "
    "WHERE a.user_id=%s AND a.brinco LIKE 'REP-%%'", (uid,))
pesos_entrada = [float(r[0]) for r in entrada]
avg_entrada = sum(pesos_entrada) / max(1, len(pesos_entrada))
pct_entrada_banda = sum(1 for p in pesos_entrada if 240 <= p <= 300) / max(1, len(pesos_entrada)) * 100
checa('zootecnia', 'Peso de entrada 8-10@ (240-300kg)', 240 <= avg_entrada <= 300,
      f"média={avg_entrada:.1f}kg ({avg_entrada/30:.2f}@), {pct_entrada_banda:.1f}% dos animais dentro da banda")

saida = q(
    "SELECT p.peso FROM animais a JOIN pesagens p ON p.animal_id=a.id AND p.data_pesagem=a.data_venda "
    "WHERE a.user_id=%s AND a.brinco LIKE 'REP-%%' AND a.preco_venda>0", (uid,))
pesos_saida = [float(r[0]) for r in saida]
avg_saida = sum(pesos_saida) / max(1, len(pesos_saida))
pct_saida_banda = sum(1 for p in pesos_saida if 600 <= p <= 660) / max(1, len(pesos_saida)) * 100
checa('zootecnia', 'Peso de venda 20-22@ (600-660kg) — média do lote', 600 <= avg_saida <= 660,
      f"média={avg_saida:.1f}kg ({avg_saida/30:.2f}@), {pct_saida_banda:.1f}% dos animais individualmente dentro "
      f"da banda (esperado <100%: outliers ruim/excepcional variam por design)")

gmd_medio = q("SELECT AVG(gmd) FROM v_gmd_analitico WHERE user_id=%s", (uid,))[0][0]
gmd_medio = float(gmd_medio) if gmd_medio is not None else 0
checa('zootecnia', 'GMD médio (v_gmd_analitico) > 0.8 kg/dia', gmd_medio > 0.8,
      f"GMD médio={gmd_medio:.3f} kg/dia")

# mortalidade: observado vs esperado (taxa anual composta sobre a exposição real de cada animal)
obitos = q("SELECT COUNT(*) FROM animais WHERE user_id=%s AND data_venda IS NOT NULL AND preco_venda=0", (uid,))[0][0]
todos_exp = q(
    "SELECT data_compra, data_nascimento, data_venda, preco_venda FROM animais WHERE user_id=%s", (uid,))
esperado = 0.0
for dc, dn, dv, pv in todos_exp:
    entrada_d = dc or dn
    if not entrada_d:
        continue
    saida_d = dv if dv else END
    dias = (saida_d - entrada_d).days
    if dias <= 0:
        continue
    esperado += 1 - (1 - 0.02) ** (dias / 365.25)
checa('zootecnia', 'Mortalidade ~2%/ano (observado vs. esperado pela exposição real)',
      esperado * 0.5 <= obitos <= esperado * 1.5,
      f"observado={obitos}, esperado≈{esperado:.1f} (taxa 2%/ano sobre dias vividos de cada animal), "
      f"{obitos/max(1,total_animais)*100:.1f}% do total cadastrado")

# ══════════════════════════════════════════════════════════════════
# 4. CUSTOS FIXOS E CONSUMO
# ══════════════════════════════════════════════════════════════════
print("\n=== 4. Custos Fixos e Consumo ===")

SALARIO_MINIMO = {2020: 1045, 2021: 1100, 2022: 1212, 2023: 1320, 2024: 1412, 2025: 1518, 2026: 1518}

vaqueiro = q(
    "SELECT YEAR(data_custo), COUNT(*), MIN(valor), MAX(valor) FROM custos_operacionais "
    "WHERE user_id=%s AND descricao LIKE '%%Vaqueiro%%' GROUP BY YEAR(data_custo) ORDER BY 1", (uid,))
for ano, n, vmin, vmax in vaqueiro:
    esperado_n = 12 if ano < 2026 else 6
    ok = n == esperado_n and float(vmin) == float(vmax) == 2200.00
    checa('custos', f'Folha Vaqueiro {ano} (R$2.200 x{esperado_n})', ok,
          f"{n} lançamentos, valor={vmin}-{vmax}")

cerqueiro = q(
    "SELECT YEAR(data_custo), COUNT(*), MIN(valor), MAX(valor) FROM custos_operacionais "
    "WHERE user_id=%s AND descricao LIKE '%%Cerqueiro%%' GROUP BY YEAR(data_custo) ORDER BY 1", (uid,))
for ano, n, vmin, vmax in cerqueiro:
    esperado_n = 12 if ano < 2026 else 6
    esperado_val = SALARIO_MINIMO.get(ano)
    ok = n == esperado_n and float(vmin) == float(vmax) == esperado_val
    checa('custos', f'Folha Cerqueiro {ano} (salário mínimo R${esperado_val} x{esperado_n})', ok,
          f"{n} lançamentos, valor={vmin}-{vmax}, esperado=R${esperado_val}")

consumo = {}
for r in q(
        "SELECT ep.nome, YEAR(em.data_mov), SUM(em.quantidade) FROM estoque_movimentacoes em "
        "JOIN estoque_produtos ep ON ep.id=em.produto_id "
        "WHERE em.user_id=%s AND em.tipo='saida' GROUP BY ep.nome, YEAR(em.data_mov)", (uid,)):
    consumo.setdefault(r[0], {})[r[1]] = float(r[2])

alvo_anual = {'Estaca de Madeira': 500, 'Arame Farpado (rolo 250m)': 10,
              'Sal Mineral / Proteinado (saco 30kg)': 200}
for produto, alvo in alvo_anual.items():
    anos_completos = [a for a in range(2020, 2026) if a in consumo.get(produto, {})]
    if not anos_completos:
        checa('custos', f'Consumo anual de {produto} (~{alvo}/ano)', False, "sem movimentações encontradas")
        continue
    media = sum(consumo[produto][a] for a in anos_completos) / len(anos_completos)
    checa('custos', f'Consumo anual de {produto} (~{alvo}/ano)', 0.7 * alvo <= media <= 1.3 * alvo,
          f"média={media:.0f}/ano nos anos completos {anos_completos}")

aftosa_doses = q(
    "SELECT COUNT(*) FROM medicacoes WHERE nome_medicamento='Febre Aftosa' AND animal_id IN "
    "(SELECT id FROM animais WHERE user_id=%s)", (uid,))[0][0]
checa('custos', 'Doses de Febre Aftosa registradas', aftosa_doses > 0, f"{aftosa_doses} doses")

anab_femea = q(
    "SELECT COUNT(*) FROM medicacoes m JOIN animais a ON a.id=m.animal_id "
    "WHERE m.nome_medicamento='Anabólico' AND a.user_id=%s AND a.sexo<>'M'", (uid,))[0][0]
anab_total = q(
    "SELECT COUNT(*) FROM medicacoes WHERE nome_medicamento='Anabólico' AND animal_id IN "
    "(SELECT id FROM animais WHERE user_id=%s)", (uid,))[0][0]
checa('custos', 'Anabólico aplicado apenas em machos', anab_femea == 0,
      f"{anab_total} doses totais, {anab_femea} em fêmeas (deve ser 0)")

# ══════════════════════════════════════════════════════════════════
# RESUMO
# ══════════════════════════════════════════════════════════════════
total = len(resultados)
passou = sum(1 for r in resultados if r[2])
falhou = total - passou
print(f"\n{'=' * 70}\nRESUMO: {passou}/{total} checagens PASSARAM, {falhou} FALHARAM\n{'=' * 70}")
if falhou:
    print("\nFalhas:")
    for secao, nome, p, detalhe in resultados:
        if not p:
            print(f"  - [{secao}] {nome}: {detalhe}")

cur.close()
conn.close()
