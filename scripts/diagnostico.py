#!/usr/bin/env python3
"""Diagnóstico de rebanho a partir de um CSV, em PDF.

Isto é ferramenta de venda, não funcionalidade: recebe a planilha de um
prospect e devolve um PDF com o que dá para dizer do rebanho dele. Por isso é
script e não rota — dado de prospect não entra na base de produção, não tem
tenant para pendurar, e não precisa do caminho de PDF do app (fila, polling,
limpeza de órfão) para gerar um arquivo uma vez.

O CSV é o mesmo da importação: brinco, sexo, data_compra, peso_kg,
valor_arroba, e as opcionais data_nascimento e raca. Planilha de prospect vem
torta — linha sem peso, brinco repetido, sexo em branco — então metade do
diagnóstico é sobre a qualidade do cadastro, que é um argumento de venda por si
só.

Rodar:
    python scripts/diagnostico.py rebanho.csv
    python scripts/diagnostico.py rebanho.csv --saida ~/diagnostico.pdf \
        --fazenda "Fazenda Boa Esperança"
"""
import argparse
import csv
import io
import os
import sys
from collections import Counter
from datetime import date
from html import escape

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.calculo import KG_POR_ARROBA  # noqa: E402

FAIXAS = ((0, 200), (200, 300), (300, 400), (400, 500), (500, 10_000))


def _numero(valor):
    try:
        return float(str(valor).replace(',', '.').strip())
    except (TypeError, ValueError):
        return None


def ler(caminho):
    """(linhas válidas, problemas). Nunca levanta por linha torta."""
    with io.open(caminho, encoding='utf-8-sig', newline='') as fh:
        leitor = csv.DictReader(fh)
        colunas = set(leitor.fieldnames or [])
        faltando = {'brinco', 'peso_kg'} - colunas
        if faltando:
            raise SystemExit(f"CSV sem coluna(s) obrigatória(s): {', '.join(sorted(faltando))}")

        validas, problemas, vistos = [], [], set()
        for i, linha in enumerate(leitor, start=2):
            brinco = (linha.get('brinco') or '').strip()
            peso = _numero(linha.get('peso_kg'))
            sexo = (linha.get('sexo') or '').strip().upper()

            if not brinco:
                problemas.append((i, 'brinco em branco'))
                continue
            if brinco in vistos:
                problemas.append((i, f"brinco repetido: {brinco}"))
                continue
            vistos.add(brinco)
            if peso is None or peso <= 0:
                problemas.append((i, f"{brinco}: peso ausente ou inválido"))
                continue
            if sexo not in ('M', 'F'):
                problemas.append((i, f"{brinco}: sexo não informado"))

            validas.append({
                'brinco': brinco,
                'sexo': sexo if sexo in ('M', 'F') else '?',
                'peso': peso,
                'arroba': _numero(linha.get('valor_arroba')),
                'raca': (linha.get('raca') or '').strip() or 'não informada',
            })
    return validas, problemas


def diagnosticar(linhas):
    pesos = [a['peso'] for a in linhas]
    arrobas = [a['arroba'] for a in linhas if a['arroba']]
    valor_ref = (sum(arrobas) / len(arrobas)) if arrobas else None

    faixas = []
    for piso, teto in FAIXAS:
        quantos = sum(1 for p in pesos if piso <= p < teto)
        faixas.append({
            'rotulo': f"{piso}–{teto} kg" if teto < 10_000 else f"acima de {piso} kg",
            'quantos': quantos,
            'pct': round(quantos * 100 / len(pesos)) if pesos else 0,
        })

    peso_total = sum(pesos)
    return {
        'cabecas': len(linhas),
        'machos': sum(1 for a in linhas if a['sexo'] == 'M'),
        'femeas': sum(1 for a in linhas if a['sexo'] == 'F'),
        'sem_sexo': sum(1 for a in linhas if a['sexo'] == '?'),
        'peso_medio': round(peso_total / len(pesos), 1) if pesos else 0,
        'peso_total': round(peso_total, 1),
        'arrobas': round(peso_total / KG_POR_ARROBA, 1) if pesos else 0,
        'mais_leve': round(min(pesos), 1) if pesos else 0,
        'mais_pesado': round(max(pesos), 1) if pesos else 0,
        'valor_arroba': valor_ref,
        'valor_rebanho': (round(peso_total / KG_POR_ARROBA * valor_ref, 2)
                          if valor_ref else None),
        'faixas': faixas,
        'racas': Counter(a['raca'] for a in linhas).most_common(5),
    }


def _brl(valor):
    return f"{valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def montar_html(d, problemas, fazenda, arquivo):
    linhas_faixa = "".join(
        f"<tr><td>{escape(f['rotulo'])}</td><td class='num'>{f['quantos']}</td>"
        f"<td><div class='barra'><span style='width:{f['pct']}%'></span></div> {f['pct']}%</td></tr>"
        for f in d['faixas'])
    linhas_raca = "".join(
        f"<tr><td>{escape(nome)}</td><td class='num'>{quantos}</td></tr>"
        for nome, quantos in d['racas'])
    lista_problemas = "".join(
        f"<li>linha {n}: {escape(msg)}</li>" for n, msg in problemas[:25])
    mais = (f"<p class='nota'>… e mais {len(problemas) - 25} ocorrência(s).</p>"
            if len(problemas) > 25 else "")
    valor = (f"R$ {_brl(d['valor_rebanho'])}" if d['valor_rebanho']
             else "— (sem valor de arroba no CSV)")

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #1C1C1A; margin: 0; }}
  h1 {{ font-size: 24px; margin: 0 0 4px; color: #3B6D11; }}
  h2 {{ font-size: 15px; margin: 28px 0 10px; color: #3B6D11;
        border-bottom: 1px solid #C0DD97; padding-bottom: 4px; }}
  .sub {{ color: #5B6A5F; font-size: 12px; margin: 0 0 20px; }}
  .cartoes {{ display: flex; flex-wrap: wrap; gap: 10px; }}
  .cartao {{ border: 1px solid #DDE5D2; border-radius: 8px; padding: 10px 14px;
             min-width: 150px; flex: 1; }}
  .cartao b {{ display: block; font-size: 20px; }}
  .cartao span {{ font-size: 11px; color: #5B6A5F; text-transform: uppercase;
                  letter-spacing: .04em; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 5px 6px; border-bottom: 1px solid #EEF2E8; }}
  th {{ font-size: 11px; text-transform: uppercase; color: #5B6A5F; }}
  .num {{ text-align: right; }}
  .barra {{ display: inline-block; width: 120px; height: 7px; background: #EEF2E8;
            border-radius: 4px; vertical-align: middle; margin-right: 6px; }}
  .barra span {{ display: block; height: 100%; background: #3B6D11; border-radius: 4px; }}
  ul {{ font-size: 12px; color: #5B6A5F; margin: 6px 0 0 18px; padding: 0; }}
  .nota {{ font-size: 11px; color: #888780; }}
  footer {{ margin-top: 32px; font-size: 10px; color: #888780;
            border-top: 1px solid #EEF2E8; padding-top: 8px; }}
</style></head><body>

<h1>Diagnóstico de rebanho</h1>
<p class="sub">{escape(fazenda)} · {escape(os.path.basename(arquivo))} ·
   {date.today().strftime('%d/%m/%Y')}</p>

<div class="cartoes">
  <div class="cartao"><span>Cabeças</span><b>{d['cabecas']}</b></div>
  <div class="cartao"><span>Peso médio</span><b>{d['peso_medio']} kg</b></div>
  <div class="cartao"><span>Peso total</span><b>{d['arrobas']} @</b></div>
  <div class="cartao"><span>Valor estimado</span><b>{valor}</b></div>
</div>

<h2>Composição</h2>
<table>
  <tr><td>Machos</td><td class="num">{d['machos']}</td></tr>
  <tr><td>Fêmeas</td><td class="num">{d['femeas']}</td></tr>
  <tr><td>Sexo não informado</td><td class="num">{d['sem_sexo']}</td></tr>
  <tr><td>Mais leve / mais pesado</td>
      <td class="num">{d['mais_leve']} kg / {d['mais_pesado']} kg</td></tr>
</table>

<h2>Distribuição por peso</h2>
<table>
  <thead><tr><th>Faixa</th><th class="num">Cabeças</th><th>Participação</th></tr></thead>
  <tbody>{linhas_faixa}</tbody>
</table>

<h2>Raças declaradas</h2>
<table><tbody>{linhas_raca or '<tr><td>Nenhuma raça informada.</td></tr>'}</tbody></table>

<h2>Qualidade do cadastro</h2>
<p class="sub" style="margin:0 0 6px;">
  {len(problemas)} ocorrência(s) em {d['cabecas'] + len(problemas)} linha(s) lidas.
  Cada uma delas é um animal que não entra em nenhum cálculo de ganho de peso.
</p>
<ul>{lista_problemas or '<li>Nenhum problema encontrado — cadastro limpo.</li>'}</ul>
{mais}

<footer>
  Gerado pelo SGG a partir do arquivo enviado. Os valores são estimativas sobre
  o que o CSV declara: peso vivo, {KG_POR_ARROBA} kg por arroba, e o valor de
  arroba informado na própria planilha.
</footer>
</body></html>"""


def escrever_pdf(html, saida):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit("playwright não instalado: pip install -r requirements.txt")

    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page()
        pagina.set_content(html, wait_until='load')
        pdf = pagina.pdf(format='A4', margin={'top': '18mm', 'bottom': '18mm',
                                              'left': '14mm', 'right': '14mm'})
        navegador.close()
    with open(saida, 'wb') as fh:
        fh.write(pdf)


def main(argv=None):
    p = argparse.ArgumentParser(description="Diagnóstico de rebanho em PDF a partir de um CSV.")
    p.add_argument('csv', help="caminho do CSV (mesmas colunas da importação)")
    p.add_argument('--saida', default=None, help="caminho do PDF (padrão: ao lado do CSV)")
    p.add_argument('--fazenda', default='Rebanho analisado', help="nome no cabeçalho")
    p.add_argument('--html', action='store_true',
                   help="escreve o HTML em vez do PDF (não precisa do Playwright)")
    args = p.parse_args(argv)

    linhas, problemas = ler(args.csv)
    if not linhas:
        raise SystemExit("Nenhuma linha válida no CSV — nada a diagnosticar.")

    html = montar_html(diagnosticar(linhas), problemas, args.fazenda, args.csv)
    saida = args.saida or os.path.splitext(args.csv)[0] + ('.html' if args.html else '.pdf')

    if args.html:
        with io.open(saida, 'w', encoding='utf-8') as fh:
            fh.write(html)
    else:
        escrever_pdf(html, saida)

    print(f"{len(linhas)} animal(is), {len(problemas)} ocorrência(s) → {saida}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
