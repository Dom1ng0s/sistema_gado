from flask import Blueprint, jsonify, render_template, Response, request, session
from flask_login import login_required, current_user
from werkzeug.exceptions import HTTPException
import csv
import io
import logging
import os as _os
import re as _re
import threading
import time
import uuid
import requests
from datetime import date
from playwright.sync_api import sync_playwright
from repositories import animal_repository, configuracao_repository, financeiro_repository
from extensions import limiter
from utils.calculo import KG_POR_ARROBA

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)


@api_bp.errorhandler(Exception)
def _handle_uncaught_error(e):
    """Handler genérico para rotas JSON: loga e devolve 500. HTTPExceptions (404, 429 do limiter etc.) seguem seu próprio fluxo."""
    if isinstance(e, HTTPException):
        raise e
    logger.error(f"Erro em {request.endpoint}: {e}", exc_info=True)
    return jsonify({'error': str(e)}), 500

# ── Cache de cotações (TTL 30 min) ──────────────────────────────────────────
_COTACOES_TTL = 30 * 60
_cotacoes_lock = threading.Lock()
_cotacoes_cache: dict = {'ts': 0.0, 'boi': [], 'novilha': []}

# ── Cache de cidades IBGE (TTL 24h) ─────────────────────────────────────────
_CIDADES_TTL = 24 * 3600
_cidades_lock = threading.Lock()
_cidades_cache: dict = {'ts': 0.0, 'dados': []}

# ── Mapa completo UF → nome (todos os 27 estados) ───────────────────────────
_MAPA_ESTADOS = {
    'AC': 'Acre',               'AL': 'Alagoas',            'AP': 'Amapá',
    'AM': 'Amazonas',           'BA': 'Bahia',              'CE': 'Ceará',
    'DF': 'Distrito Federal',   'ES': 'Espírito Santo',     'GO': 'Goiás',
    'MA': 'Maranhão',           'MT': 'Mato Grosso',        'MS': 'Mato Grosso do Sul',
    'MG': 'Minas Gerais',       'PA': 'Pará',               'PB': 'Paraíba',
    'PR': 'Paraná',             'PE': 'Pernambuco',         'PI': 'Piauí',
    'RJ': 'Rio de Janeiro',     'RN': 'Rio Grande do Norte','RS': 'Rio Grande do Sul',
    'RO': 'Rondônia',           'RR': 'Roraima',            'SC': 'Santa Catarina',
    'SP': 'São Paulo',          'SE': 'Sergipe',            'TO': 'Tocantins',
}

_PDF_DIR = '/tmp'
_PDF_MAX_AGE = 3600  # 1h — jobs abandonados (.pdf/.error/.pending) viram lixo em /tmp
_UUID_RE = _re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')


def _limpar_pdfs_orfaos() -> None:
    """Remove sgg_pdf_* com mais de 1h ao criar um job novo — limpeza
    oportunística, sem worker/cron dedicado.
    ponytail: best-effort, nunca propaga erro para a geração do relatório."""
    corte = time.time() - _PDF_MAX_AGE
    try:
        with _os.scandir(_PDF_DIR) as it:
            for entry in it:
                if entry.name.startswith('sgg_pdf_') and entry.stat().st_mtime < corte:
                    try:
                        _os.remove(entry.path)
                    except OSError:
                        pass
    except OSError:
        pass


def _csv_response(filename: str, header: list, rows: list) -> Response:
    """Serializa linhas já formatadas em CSV (BOM utf-8) e devolve como anexo."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return Response(
        buf.getvalue().encode('utf-8-sig'),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


def _fetch_cotacoes_github() -> tuple[list, list]:
    """Retorna (boi, novilha) com cache em memória de 30 minutos."""
    now = time.time()
    with _cotacoes_lock:
        if now - _cotacoes_cache['ts'] < _COTACOES_TTL:
            return _cotacoes_cache['boi'], _cotacoes_cache['novilha']

    base = "https://raw.githubusercontent.com/dom1ng0s/gado-scraper/main"

    def _get(endpoint: str) -> list:
        try:
            r = requests.get(f"{base}/{endpoint}", timeout=5)
            if r.status_code != 200:
                return []
            dados = r.json()
            return dados if isinstance(dados, list) else []
        except Exception:
            return []

    boi = _get("cotacoes_boi_hoje.json")
    novilha = _get("cotacoes_novilha_hoje.json")

    if boi or novilha:
        with _cotacoes_lock:
            _cotacoes_cache.update({'ts': now, 'boi': boi, 'novilha': novilha})

    return boi, novilha


def _gerar_pdf_bg(job_id: str, html: str) -> None:
    pdf_path  = f"{_PDF_DIR}/sgg_pdf_{job_id}.pdf"
    pend_path = f"{_PDF_DIR}/sgg_pdf_{job_id}.pending"
    err_path  = f"{_PDF_DIR}/sgg_pdf_{job_id}.error"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(html, wait_until='load')
            pdf_bytes = page.pdf(format='A4', margin={
                'top': '20mm', 'bottom': '20mm',
                'left': '15mm', 'right': '15mm',
            })
            browser.close()
        with open(pdf_path, 'wb') as f:
            f.write(pdf_bytes)
    except Exception as e:
        logger.error(f"Erro PDF bg job {job_id}: {e}", exc_info=True)
        with open(err_path, 'w') as f:
            f.write(str(e))
    finally:
        try:
            _os.unlink(pend_path)
        except FileNotFoundError:
            pass

@api_bp.route('/graficos')
@login_required
@limiter.limit("60 per minute")
def graficos_page():
    animais_abaixo_meta = []
    gmd_meta_atual = 0.800
    try:
        cfg = configuracao_repository.get_configuracao(current_user.id)
        gmd_meta_atual = float(cfg[3]) if (cfg and cfg[3] is not None) else 0.800
        animais_abaixo_meta = animal_repository.get_animais_abaixo_gmd_meta(current_user.id, gmd_meta_atual)
    except Exception as e:
        logger.error(f"Erro ao carregar animais abaixo da meta: {e}", exc_info=True)

    return render_template('graficos.html', animais_abaixo_meta=animais_abaixo_meta)

def _with_cache(response, max_age=60):
    """Adiciona Cache-Control private ao response JSON."""
    response.headers['Cache-Control'] = f'private, max-age={max_age}'
    return response


@api_bp.route('/api/graficos/sexo')
@login_required
@limiter.limit("60 per minute")
def graficos_sexo():
    rows = animal_repository.get_contagem_por_sexo(current_user.id)
    return _with_cache(jsonify({sexo: qtd for sexo, qtd in rows}))

@api_bp.route('/api/graficos/peso')
@login_required
@limiter.limit("60 per minute")
def graficos_peso():
    rows = animal_repository.get_pesos_atuais_rebanho(current_user.id)
    cat_peso = {'Menos de 10@': 0, '10@ a 15@': 0, '15@ a 20@': 0, 'Mais de 20@': 0}
    for (p_kg,) in rows:
        p_arr = float(p_kg) / KG_POR_ARROBA
        if p_arr < 10:
            cat_peso['Menos de 10@'] += 1
        elif 10 <= p_arr < 15:
            cat_peso['10@ a 15@'] += 1
        elif 15 <= p_arr < 20:
            cat_peso['15@ a 20@'] += 1
        else:
            cat_peso['Mais de 20@'] += 1
    return _with_cache(jsonify(cat_peso))

@api_bp.route('/api/graficos/gmd')
@login_required
@limiter.limit("60 per minute")
def graficos_gmd():
    sexo = request.args.get('sexo') if request.args.get('sexo') in ('M', 'F') else None
    gmd_medio = animal_repository.get_gmd_medio_rebanho(current_user.id, sexo=sexo)
    return _with_cache(jsonify({'gmd_medio': gmd_medio}))


@api_bp.route('/api/animais/gmd-lote')
@login_required
@limiter.limit("120 per minute")
def gmd_lote():
    """Retorna peso_final e gmd para até 50 IDs — bypassa a view CTE."""
    ids_raw = request.args.get('ids', '').strip()
    if not ids_raw:
        return jsonify({})
    try:
        animal_ids = [int(i) for i in ids_raw.split(',') if i.strip()]
    except ValueError:
        return jsonify({'error': 'IDs inválidos'}), 400
    if len(animal_ids) > 50:
        return jsonify({'error': 'Máximo 50 IDs por requisição'}), 400
    resultado = animal_repository.get_gmd_lote(animal_ids, current_user.id)
    return jsonify(resultado)


@api_bp.route('/api/dashboard-summary')
@login_required
@limiter.limit("60 per minute")
def dashboard_summary():
    """Retorna sexo + GMD + alertas em uma única request — 2 queries vs 3 antes."""
    uid = current_user.id
    sexo_filtro = request.args.get('sexo') if request.args.get('sexo') in ('M', 'F') else None
    origem_filtro = request.args.get('origem') if request.args.get('origem') == 'fazenda' else None
    rows_sexo = animal_repository.get_contagem_por_sexo(uid, origem=origem_filtro)
    sexo = {s: q for s, q in rows_sexo}

    rows_alertas = animal_repository.get_animais_abaixo_gmd_medio(uid, sexo=sexo_filtro, origem=origem_filtro)

    if rows_alertas:
        gmd_medio  = round(float(rows_alertas[0][3]), 3)
        limite     = round(float(rows_alertas[0][5]), 3)
        alertas    = [{'id': r[0], 'brinco': r[1], 'gmd_atual': round(float(r[2]), 3)} for r in rows_alertas]
    else:
        gmd_medio = round(animal_repository.get_gmd_medio_rebanho(uid, sexo=sexo_filtro, origem=origem_filtro), 3)
        limite    = None
        alertas   = []

    return _with_cache(jsonify({
        'sexo': sexo,
        'gmd': {'gmd_medio': gmd_medio},
        'alertas': {
            'gmd_media_rebanho': gmd_medio,
            'gmd_limite_inferior': limite,
            'total': len(alertas),
            'animais': alertas,
        },
    }))

@api_bp.route('/api/v1/relatorio/pdf', methods=['POST'])
@login_required
@limiter.limit("6 per minute")
def relatorio_pdf():
    """Inicia geração de PDF em background. Retorna job_id para polling."""
    config    = configuracao_repository.get_configuracao(current_user.id)
    fluxo     = financeiro_repository.get_fluxo_caixa(current_user.id)
    animais   = animal_repository.get_animais_com_gmd(current_user.id)
    gmds      = [float(a[5]) for a in animais if a[5] is not None]
    gmd_medio = sum(gmds) / len(gmds) if gmds else 0.0

    html = render_template('relatorio_pdf.html',
                           config=config, fluxo=fluxo, animais=animais,
                           gmd_medio=gmd_medio,
                           data_geracao=date.today().strftime('%d/%m/%Y'))

    _limpar_pdfs_orfaos()
    job_id = str(uuid.uuid4())
    jobs = session.get('pdf_jobs', [])
    jobs = (jobs[-9:] if len(jobs) >= 10 else jobs) + [job_id]
    session['pdf_jobs'] = jobs
    open(f"{_PDF_DIR}/sgg_pdf_{job_id}.pending", 'w').close()
    threading.Thread(target=_gerar_pdf_bg, args=(job_id, html), daemon=True).start()

    return jsonify({'job_id': job_id})


@api_bp.route('/api/v1/relatorio/pdf/<job_id>/status')
@login_required
def pdf_status(job_id: str):
    if not _UUID_RE.match(job_id):
        return jsonify({'status': 'not_found'}), 404
    if job_id not in session.get('pdf_jobs', []):
        return jsonify({'status': 'not_found'}), 404
    if _os.path.exists(f"{_PDF_DIR}/sgg_pdf_{job_id}.pdf"):
        return jsonify({'status': 'done'})
    if _os.path.exists(f"{_PDF_DIR}/sgg_pdf_{job_id}.error"):
        return jsonify({'status': 'error'})
    if _os.path.exists(f"{_PDF_DIR}/sgg_pdf_{job_id}.pending"):
        return jsonify({'status': 'pending'})
    return jsonify({'status': 'not_found'}), 404


@api_bp.route('/api/v1/relatorio/pdf/<job_id>/download')
@login_required
def pdf_download(job_id: str):
    if not _UUID_RE.match(job_id):
        return jsonify({'error': 'Invalid job ID'}), 400
    if job_id not in session.get('pdf_jobs', []):
        return jsonify({'error': 'PDF não encontrado ou expirado'}), 404
    pdf_path = f"{_PDF_DIR}/sgg_pdf_{job_id}.pdf"
    if not _os.path.exists(pdf_path):
        return jsonify({'error': 'PDF não encontrado ou expirado'}), 404
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()
    try:
        _os.unlink(pdf_path)
    except Exception:
        pass
    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={'Content-Disposition': 'attachment; filename="relatorio_rebanho.pdf"'},
    )


@api_bp.route('/api/v1/export/animais.csv')
@login_required
@limiter.limit("10 per minute")
def export_animais_csv():
    # get_animais_com_gmd: id(0) brinco(1) sexo(2) raca(3) data_compra(4) gmd(5) dias(6) peso_final(7)
    rows = animal_repository.get_animais_com_gmd(current_user.id)
    linhas = [[
        r[0],
        r[1],
        'Macho' if r[2] == 'M' else 'Fêmea',
        r[3] or '',
        r[4].strftime('%d/%m/%Y') if r[4] else '',
        f"{float(r[5]):.3f}" if r[5] is not None else '',
        r[6] if r[6] is not None else '',
        f"{float(r[7]):.1f}" if r[7] is not None else '',
    ] for r in rows]
    return _csv_response(
        'animais.csv',
        ['ID', 'Brinco', 'Sexo', 'Raça', 'Data Compra', 'GMD (kg/dia)', 'Dias em Fazenda', 'Peso Atual (kg)'],
        linhas,
    )


@api_bp.route('/api/financeiro/custos')
@login_required
@limiter.limit("60 per minute")
def custos_por_ano():
    """Retorna detalhamento de custos do ano em JSON — usado pelo lazy-load do financeiro."""
    ano = request.args.get('ano', date.today().year, type=int)
    rows = financeiro_repository.get_custos_por_ano(current_user.id, ano)
    return jsonify([{
        'data':      r[0].strftime('%d/%m/%Y') if r[0] else '',
        'categoria': r[1] or '',
        'descricao': r[2] or '',
        'valor':     float(r[3]) if r[3] is not None else 0.0,
        'qtd':       int(r[4]) if r[4] is not None else 1,
        'obs':       r[5] or '',
    } for r in rows])


@api_bp.route('/api/v1/export/financeiro.csv')
@login_required
@limiter.limit("10 per minute")
def export_financeiro_csv():
    ano = request.args.get('ano', date.today().year, type=int)
    rows = financeiro_repository.get_custos_por_ano(current_user.id, ano)
    linhas = [[
        r[0].strftime('%d/%m/%Y') if r[0] else '',
        r[1] or '',
        r[2] or '',
        f"{float(r[3]):.2f}" if r[3] is not None else '',
        int(r[4]) if r[4] is not None else 1,
        r[5] or '',
    ] for r in rows]
    return _csv_response(
        f'financeiro_{ano}.csv',
        ['Data', 'Categoria', 'Tipo de Custo', 'Valor (R$)', 'Qtd', 'Descrição'],
        linhas,
    )


@api_bp.route('/api/v1/alertas/gmd')
@login_required
@limiter.limit("30 per minute")
def alerta_gmd():
    rows = animal_repository.get_animais_abaixo_gmd_medio(current_user.id)
    if not rows:
        gmd_media = animal_repository.get_gmd_medio_rebanho(current_user.id)
        return jsonify({
            'gmd_media_rebanho': round(gmd_media, 3),
            'total': 0,
            'animais': [],
        })
    gmd_media = round(float(rows[0][3]), 3)
    limite = round(float(rows[0][5]), 3)
    return jsonify({
        'gmd_media_rebanho': gmd_media,
        'gmd_limite_inferior': limite,
        'total': len(rows),
        'animais': [
            {'id': r[0], 'brinco': r[1], 'gmd_atual': round(float(r[2]), 3)}
            for r in rows
        ],
    })

# --- FIM DAS ROTAS DE GRÁFICOS ---

def _fetch_cidades_ibge() -> list:
    """Retorna lista de cidades com cache em memória de 24h."""
    now = time.time()
    with _cidades_lock:
        if now - _cidades_cache['ts'] < _CIDADES_TTL and _cidades_cache['dados']:
            return _cidades_cache['dados']

    try:
        url = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            logger.error(f"Erro IBGE: Status {response.status_code}")
            return _cidades_cache['dados']  # retorna cache antigo se disponível

        dados_brutos = response.json()
        cidades_formatadas = []
        for item in dados_brutos:
            try:
                cidades_formatadas.append({
                    "nome": item['nome'],
                    "uf": item['microrregiao']['mesorregiao']['UF']['sigla']
                })
            except (KeyError, TypeError):
                continue

        with _cidades_lock:
            _cidades_cache.update({'ts': now, 'dados': cidades_formatadas})
        return cidades_formatadas
    except Exception as e:
        logger.error(f"Erro fetch IBGE: {e}", exc_info=True)
        return _cidades_cache['dados']


@api_bp.route('/proxy-cidades')
@limiter.limit("10 per minute")
def proxy_cidades():
    """Cidades brasileiras via IBGE — cache de 24h, evita chamada por request."""
    return jsonify(_fetch_cidades_ibge())

@api_bp.route('/cotacoes-regionais')
@login_required
@limiter.limit("30 per minute")
def cotacoes_regionais():
    uf_usuario = None
    res = configuracao_repository.get_configuracao(current_user.id)
    if res and res[1]:
        partes = res[1].split('-')
        if len(partes) > 1:
            uf_usuario = partes[-1].strip().upper()

    if not uf_usuario:
        return jsonify({'erro': 'Localização não configurada'}), 404

    boi_todos, novilha_todos = _fetch_cotacoes_github()

    nome_completo = _MAPA_ESTADOS.get(uf_usuario, '')

    def filtrar(dados):
        out = []
        for item in dados:
            praca = item.get('praca', '').upper()
            if praca.startswith(uf_usuario) or praca == uf_usuario or \
                    (nome_completo and praca == nome_completo.upper()):
                out.append(item)
        return out

    return jsonify({
        'uf': uf_usuario,
        'boi': filtrar(boi_todos),
        'novilha': filtrar(novilha_todos),
    })


@api_bp.route('/cotacoes-brasil')
@login_required
@limiter.limit("30 per minute")
def cotacoes_brasil():
    """Retorna cotações de todas as praças — servido do cache compartilhado."""
    boi, novilha = _fetch_cotacoes_github()
    return jsonify({'boi': boi, 'novilha': novilha})
