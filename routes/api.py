from flask import Blueprint, jsonify, Response, request, session, g
from flask_login import login_required, current_user, login_user, logout_user
from flask_wtf.csrf import generate_csrf
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
import csv
import io
import logging
import secrets
import threading
import time
from datetime import date, datetime
import requests
from db_config import get_db_cursor
from models import User
from repositories import (
    acesso_repository,
    animal_repository,
    auth_repository,
    configuracao_repository,
    estoque_repository,
    financeiro_repository,
    pasto_repository,
    reproducao_repository,
    sanitario_repository,
)
from services import pesagem as pesagem_service
from extensions import limiter
from utils.calculo import KG_POR_ARROBA
from utils.carencia import CARENCIA_PADRAO, dias_carencia_sugerido
from utils.plano import PLANO_PADRAO, pode_cadastrar, resumo as resumo_plano

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)


@api_bp.errorhandler(Exception)
def _handle_uncaught_error(e):
    """Handler genérico para rotas JSON: loga e devolve 500.

    HTTPException volta como ela mesma — devolvida, não relançada: relançar de
    dentro do handler escapa do `handle_http_exception` e o 401/404/429 chega
    ao cliente como 500. Ficou invisível enquanto havia tela de login (o
    Flask-Login redirecionava em vez de abortar com 401), e aparece em toda
    requisição sem sessão agora que a resposta certa é 401.
    """
    if isinstance(e, HTTPException):
        return e
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


def _with_cache(response, max_age=60):
    """Adiciona Cache-Control private ao response JSON."""
    response.headers['Cache-Control'] = f'private, max-age={max_age}'
    return response


def _iso(val):
    """Serializa date/datetime para string ISO-8601 ou None."""
    if val is None:
        return None
    if isinstance(val, (date, datetime)):
        return val.isoformat()
    return str(val)


def _payload_json() -> dict:
    """Lê corpo JSON ou form da requisição como dicionário."""
    dados = request.get_json(silent=True)
    if isinstance(dados, dict):
        return dados
    if request.form:
        return request.form.to_dict()
    return {}


def _serializar_plano(farm_id: int) -> dict:
    """Retorna o resumo do plano da fazenda serializável em JSON."""
    plano_raw = getattr(g, 'plano', None)
    if not plano_raw or getattr(current_user, 'farm_id', None) != farm_id:
        try:
            plano_raw = configuracao_repository.get_plano(farm_id)
        except Exception:
            plano_raw = dict(PLANO_PADRAO)
    cabecas = animal_repository.contar_cabecas_ativas(farm_id)
    res = resumo_plano(plano_raw or PLANO_PADRAO, cabecas)
    if isinstance(res.get('trial_ends_at'), (date, datetime)):
        res['trial_ends_at'] = res['trial_ends_at'].isoformat()
    return res


def _build_me_payload(user: User) -> dict:
    """Constrói o payload completo de sessão para /api/auth/me e /api/auth/login."""
    cfg = configuracao_repository.get_configuracao(user.farm_id)
    nomes = acesso_repository.nomes_de_fazendas(user.fazendas)
    nome_fazenda = (
        cfg[0] if (cfg and cfg[0])
        else nomes.get(user.farm_id, user.username)
    )
    gmd_meta = float(cfg[3]) if (cfg and cfg[3] is not None) else 0.8
    fazendas_lista = [
        {
            'id': fid,
            'nome': nomes.get(fid, user.username if fid == user.id else f'Fazenda #{fid}'),
            'papel': 'dono' if fid == user.id else user.acessos.get(fid, 'dono'),
            'atual': fid == user.farm_id,
        }
        for fid in user.fazendas
    ]
    return {
        'ok': True,
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'farm_id': user.farm_id,
        'nome_fazenda': nome_fazenda,
        'cidade_estado': cfg[1] if cfg else None,
        'area_total': float(cfg[2]) if (cfg and cfg[2] is not None) else None,
        'gmd_meta': gmd_meta,
        'papel': user.papel,
        'fazendas': fazendas_lista,
        'plano': _serializar_plano(user.farm_id),
        'csrf_token': generate_csrf(),
    }


def _formatar_carencia(c) -> dict:
    """Converte linha de vw_animais_em_carencia em dict JSON."""
    return {
        'animal_id': c[0],
        'brinco': c[1],
        'medicacao_id': c[2],
        'nome_medicamento': c[3],
        'data_aplicacao': _iso(c[4]),
        'dias_carencia': int(c[5]) if c[5] is not None else 0,
        'data_liberacao': _iso(c[6]),
        'dias_restantes': int(c[7]) if c[7] is not None else 0,
    }


# ══════════════════════════════════════════════════════════════════════════════
# AUTENTICAÇÃO E SESSÃO
# ══════════════════════════════════════════════════════════════════════════════

@api_bp.route('/api/auth/login', methods=['POST'])
@limiter.limit("20 per minute")
def auth_login():
    dados = _payload_json()
    identificador = (
        dados.get('username')
        or dados.get('email')
        or dados.get('login')
        or ''
    ).strip()
    senha = dados.get('password') or dados.get('senha') or ''

    if not identificador or not senha:
        return jsonify({'error': 'Usuário/e-mail e senha são obrigatórios'}), 400

    row = auth_repository.get_user_by_email(identificador)
    if not row:
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT id, username, password_hash, email FROM usuarios "
                "WHERE (username = %s OR LOWER(email) = LOWER(%s)) AND ativo = 1",
                (identificador, identificador),
            )
            row = cursor.fetchone()

    if not row or not check_password_hash(row[2], senha):
        return jsonify({'error': 'Credenciais inválidas'}), 401

    user = User.get_user_id(row[0], session.get('farm_id'))
    if not user:
        return jsonify({'error': 'Conta inativa ou não encontrada'}), 401

    login_user(user)
    session['farm_id'] = user.farm_id
    return jsonify(_build_me_payload(user))


@api_bp.record_once
def _exempt_auth_routes(state):
    csrf_ext = state.app.extensions.get('csrf')
    if csrf_ext:
        csrf_ext.exempt(auth_login)


@api_bp.route('/api/auth/logout', methods=['POST'])
@login_required
def auth_logout():
    session.pop('farm_id', None)
    logout_user()
    return jsonify({'ok': True})


@api_bp.route('/api/auth/me', methods=['GET'])
@login_required
def auth_me():
    return jsonify(_build_me_payload(current_user))


@api_bp.route('/api/auth/trocar-fazenda', methods=['POST'])
@login_required
def auth_trocar_fazenda():
    dados = _payload_json()
    raw_fid = dados.get('farm_id')
    try:
        fid = int(raw_fid)
    except (TypeError, ValueError):
        return jsonify({'error': 'farm_id inválido'}), 400

    if fid not in current_user.fazendas:
        return jsonify({'error': 'Sem acesso à fazenda informada'}), 403

    session['farm_id'] = fid
    resolved_fid, novo_papel = User.resolver_fazenda(
        current_user.id,
        current_user.acessos,
        escolhida=fid,
        tem_fazenda_propria=current_user.tem_fazenda_propria,
    )
    current_user.farm_id = resolved_fid
    current_user.papel = novo_papel
    return jsonify(_build_me_payload(current_user))


# ══════════════════════════════════════════════════════════════════════════════
# REBANHO E CURRAL
# ══════════════════════════════════════════════════════════════════════════════

@api_bp.route('/api/animais', methods=['GET'])
@login_required
@limiter.limit("60 per minute")
def listar_animais():
    uid = current_user.farm_id
    rows = animal_repository.get_animais_com_gmd(uid)
    carencias_rows = sanitario_repository.get_carencias_ativas(uid)
    lotes_rows = animal_repository.get_lotes(uid)
    racas = animal_repository.get_racas_distintas(uid)

    # Enriquecer com lote_id, codigo_lote, preco_compra, data_nascimento
    extras_por_id = {}
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT a.id, a.lote_id, l.codigo_lote, a.preco_compra, "
            "       a.data_nascimento, a.pai_id, a.mae_id "
            "FROM animais a "
            "LEFT JOIN lotes l ON l.id = a.lote_id "
            "WHERE a.user_id = %s AND a.deleted_at IS NULL AND a.data_venda IS NULL",
            (uid,),
        )
        for erow in cursor.fetchall():
            extras_por_id[erow[0]] = {
                'lote_id': erow[1],
                'codigo_lote': erow[2],
                'preco_compra': float(erow[3]) if erow[3] is not None else None,
                'data_nascimento': _iso(erow[4]),
                'pai_id': erow[5],
                'mae_id': erow[6],
            }

    carencias_fmt = [_formatar_carencia(c) for c in carencias_rows]
    carencia_por_animal = {}
    for c_dict in carencias_fmt:
        aid = c_dict['animal_id']
        if aid not in carencia_por_animal:
            carencia_por_animal[aid] = c_dict

    animais = []
    for r in rows:
        aid = r[0]
        extra = extras_por_id.get(aid, {})
        peso_final = round(float(r[7]), 1) if r[7] is not None else None
        animais.append({
            'id': aid,
            'brinco': r[1],
            'sexo': r[2],
            'raca': r[3] or '',
            'data_compra': _iso(r[4]),
            'gmd': round(float(r[5]), 3) if r[5] is not None else None,
            'dias': int(r[6]) if r[6] is not None else None,
            'peso_final': peso_final,
            'peso_atual': peso_final,
            'arrobas': round(peso_final / KG_POR_ARROBA, 1) if peso_final is not None else None,
            'lote_id': extra.get('lote_id'),
            'codigo_lote': extra.get('codigo_lote'),
            'preco_compra': extra.get('preco_compra'),
            'data_nascimento': extra.get('data_nascimento'),
            'pai_id': extra.get('pai_id'),
            'mae_id': extra.get('mae_id'),
            'em_carencia': aid in carencia_por_animal,
            'carencia': carencia_por_animal.get(aid),
        })

    return jsonify({
        'animais': animais,
        'carencias': carencias_fmt,
        'lotes': [{'id': l[0], 'codigo_lote': l[1]} for l in lotes_rows],
        'racas': racas,
        'total': len(animais),
    })


@api_bp.route('/api/animais', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def criar_animal():
    uid = current_user.farm_id
    dados = _payload_json()
    plano_atual = getattr(g, 'plano', None) or configuracao_repository.get_plano(uid) or PLANO_PADRAO
    cabecas = animal_repository.contar_cabecas_ativas(uid)

    # Suporte opcional a cadastro de lote se `animais` vier na carga
    if isinstance(dados.get('animais'), list) and dados.get('codigo_lote'):
        itens = dados['animais']
        if not itens:
            return jsonify({'error': 'Informe ao menos um animal no lote'}), 400
        ok, msg = pode_cadastrar(plano_atual, cabecas, len(itens))
        if not ok:
            return jsonify({'error': msg}), 400
        codigo_lote = str(dados.get('codigo_lote', '')).strip()
        descricao = str(dados.get('descricao', '')).strip()
        data_compra = dados.get('data_compra') or date.today().isoformat()
        raca = dados.get('raca')
        animais_data = []
        for item in itens:
            brinco_i = str(item.get('brinco', '')).strip()
            sexo_i = str(item.get('sexo', 'M')).strip().upper()
            peso_i = float(item.get('peso') or item.get('peso_entrada') or 0)
            custo_i = float(item.get('preco_compra') or item.get('custo') or 0)
            if not brinco_i or sexo_i not in ('M', 'F') or peso_i <= 0:
                return jsonify({'error': f'Dados inválidos para o brinco {brinco_i or "?"}'}), 400
            if animal_repository.check_brinco_exists(brinco_i, uid):
                return jsonify({'error': f"Brinco '{brinco_i}' já cadastrado"}), 400
            animais_data.append((brinco_i, sexo_i, peso_i, custo_i))
        lote_id = animal_repository.cadastrar_lote(
            uid, codigo_lote, descricao, data_compra, animais_data,
            raca=raca, registrado_por=current_user.id,
        )
        return jsonify({'ok': True, 'lote_id': lote_id, 'cadastrados': len(animais_data)}), 201

    ok, msg = pode_cadastrar(plano_atual, cabecas, 1)
    if not ok:
        return jsonify({'error': msg}), 400

    brinco = str(dados.get('brinco', '')).strip()
    sexo = str(dados.get('sexo', '')).strip().upper()
    if not brinco:
        return jsonify({'error': 'Brinco é obrigatório'}), 400
    if sexo not in ('M', 'F'):
        return jsonify({'error': "Sexo deve ser 'M' ou 'F'"}), 400
    if animal_repository.check_brinco_exists(brinco, uid):
        return jsonify({'error': f"Brinco '{brinco}' já existe no rebanho"}), 400

    raca = dados.get('raca')
    data_compra = dados.get('data_compra') or None
    data_nascimento = dados.get('data_nascimento') or None
    if not data_compra and not data_nascimento:
        data_compra = date.today().isoformat()

    preco_compra = float(dados['preco_compra']) if dados.get('preco_compra') not in (None, '') else None
    peso_raw = dados.get('peso_entrada') if dados.get('peso_entrada') not in (None, '') else dados.get('peso')
    peso_entrada = float(peso_raw) if peso_raw not in (None, '') else None
    mae_id = int(dados['mae_id']) if dados.get('mae_id') not in (None, '') else None
    pai_id = int(dados['pai_id']) if dados.get('pai_id') not in (None, '') else None

    animal_id = animal_repository.cadastrar_animal(
        brinco=brinco,
        sexo=sexo,
        data_compra=data_compra,
        preco_compra=preco_compra,
        peso_entrada=peso_entrada,
        user_id=uid,
        data_nascimento=data_nascimento,
        mae_id=mae_id,
        pai_id=pai_id,
        raca=raca,
        registrado_por=current_user.id,
    )
    return jsonify({'ok': True, 'id': animal_id, 'brinco': brinco}), 201


@api_bp.route('/api/animais/<int:animal_id>', methods=['GET'])
@login_required
@limiter.limit("60 per minute")
def detalhe_animal(animal_id: int):
    uid = current_user.farm_id
    row = animal_repository.get_animal_by_id(animal_id, uid)
    if not row or row[10] is not None:
        return jsonify({'error': 'Animal não encontrado'}), 404

    pesagens_rows = animal_repository.get_pesagens_by_animal(animal_id)
    medicacoes_rows = animal_repository.get_medicacoes_by_animal(animal_id)
    gmd_row = animal_repository.get_gmd_by_animal(animal_id)
    progenie_rows = animal_repository.get_progenie_by_touro(animal_id, uid)
    carencias_rows = sanitario_repository.get_carencias_ativas(uid, [animal_id])

    pai_info = None
    if row[11]:
        pai_row = animal_repository.get_animal_by_id(row[11], uid)
        if pai_row:
            pai_info = {'id': pai_row[0], 'brinco': pai_row[1], 'raca': pai_row[3]}

    mae_info = None
    if row[12]:
        mae_row = animal_repository.get_animal_by_id(row[12], uid)
        if mae_row:
            mae_info = {'id': mae_row[0], 'brinco': mae_row[1], 'raca': mae_row[3]}

    pesagens = [
        {
            'id': p[0],
            'animal_id': p[1],
            'data_pesagem': _iso(p[2]),
            'peso': float(p[3]) if p[3] is not None else 0.0,
            'arrobas': round(float(p[3]) / KG_POR_ARROBA, 1) if p[3] is not None else 0.0,
            'registrado_por': p[5],
        }
        for p in pesagens_rows
    ]

    medicacoes = [
        {
            'id': m[0],
            'animal_id': m[1],
            'data_aplicacao': _iso(m[2]),
            'nome_medicamento': m[3],
            'custo': float(m[4]) if m[4] is not None else 0.0,
            'observacoes': m[5] or '',
            'dias_carencia': int(m[6]) if m[6] is not None else 0,
            'data_liberacao': _iso(m[7]),
            'registrado_por': m[8],
        }
        for m in medicacoes_rows
    ]

    progenie = [
        {
            'id': f[0],
            'brinco': f[1],
            'sexo': f[2],
            'data_compra': _iso(f[3]),
            'gmd': round(float(f[4]), 3) if f[4] is not None else None,
            'papel': f[5],
        }
        for f in progenie_rows
    ]

    reproducao_lista = []
    historico_vaca = None
    if row[2] == 'F':
        rep_rows = reproducao_repository.get_reproducao_by_vaca(animal_id, uid)
        reproducao_lista = [
            {
                'id': r[0],
                'data_cobertura': _iso(r[1]),
                'data_parto': _iso(r[2]),
                'resultado': r[3],
                'touro_brinco': r[4],
                'touro_externo': r[5],
                'diagnostico': r[6],
                'data_diagnostico': _iso(r[7]),
                'data_parto_prevista': _iso(r[8]),
            }
            for r in rep_rows
        ]
        hv = animal_repository.get_historico_reproducao(animal_id, uid)
        if hv:
            historico_vaca = {
                'vaca_id': hv[0],
                'total_coberturas': int(hv[1] or 0),
                'partos_vivos': int(hv[2] or 0),
                'taxa_sucesso': float(hv[3] or 0.0),
                'primeira_cobertura': _iso(hv[4]),
                'ultima_cobertura': _iso(hv[5]),
            }

    peso_atual = (
        float(gmd_row[0]) if gmd_row and gmd_row[0] is not None
        else (pesagens[0]['peso'] if pesagens else None)
    )
    peso_entrada = pesagens[-1]['peso'] if pesagens else None

    return jsonify({
        'id': row[0],
        'brinco': row[1],
        'sexo': row[2],
        'raca': row[3] or '',
        'data_compra': _iso(row[4]),
        'preco_compra': float(row[5]) if row[5] is not None else None,
        'data_venda': _iso(row[6]),
        'preco_venda': float(row[7]) if row[7] is not None else None,
        'lote_id': row[9],
        'pai_id': row[11],
        'mae_id': row[12],
        'data_nascimento': _iso(row[13]),
        'peso_entrada': peso_entrada,
        'peso_atual': peso_atual,
        'ganho_total': float(gmd_row[1]) if gmd_row and gmd_row[1] is not None else None,
        'dias': int(gmd_row[2]) if gmd_row and gmd_row[2] is not None else None,
        'gmd': round(float(gmd_row[3]), 3) if gmd_row and gmd_row[3] is not None else None,
        'pai': pai_info,
        'mae': mae_info,
        'pesagens': pesagens,
        'medicacoes': medicacoes,
        'carencias': [_formatar_carencia(c) for c in carencias_rows],
        'progenie': progenie,
        'reproducao': reproducao_lista,
        'historico_reproducao': historico_vaca,
    })


@api_bp.route('/api/animais/<int:animal_id>', methods=['DELETE'])
@login_required
def excluir_animal(animal_id: int):
    ok = animal_repository.soft_delete_animal(animal_id, current_user.farm_id)
    if not ok:
        return jsonify({'error': 'Animal não encontrado'}), 404
    return jsonify({'ok': True, 'id': animal_id})


@api_bp.route('/api/lixeira', methods=['GET'])
@login_required
def listar_lixeira():
    termo = request.args.get('termo', '').strip() or None
    rows = animal_repository.get_animais_lixeira_paginados(
        current_user.farm_id, limit=200, offset=0, termo=termo
    )
    animais = [
        {
            'id': r[0],
            'brinco': r[1],
            'sexo': r[2],
            'deleted_at': _iso(r[3]),
        }
        for r in rows
    ]
    return jsonify({'animais': animais, 'total': len(animais)})


@api_bp.route('/api/lixeira/<int:animal_id>/restaurar', methods=['POST'])
@login_required
def restaurar_lixeira(animal_id: int):
    animal_repository.restore_animal(animal_id, current_user.farm_id)
    return jsonify({'ok': True, 'id': animal_id})


@api_bp.route('/api/pesagens', methods=['POST'])
@login_required
@limiter.limit("60 per minute")
def registrar_pesagens():
    uid = current_user.farm_id
    dados = _payload_json()
    data_padrao = (
        dados.get('data_pesagem')
        or dados.get('data')
        or date.today().isoformat()
    )

    itens = dados.get('pesagens')
    if not isinstance(itens, list):
        itens = [dados]

    if not itens:
        return jsonify({'error': 'Nenhuma pesagem informada'}), 400

    registrados = []
    erros = []
    for item in itens:
        if not isinstance(item, dict):
            continue
        peso = item.get('peso')
        data_p = item.get('data') or item.get('data_pesagem') or data_padrao
        aid_raw = item.get('animal_id') or item.get('id')
        aid = int(aid_raw) if aid_raw not in (None, '') else None
        brinco = str(item.get('brinco') or '').strip() or None

        alvo_id, erro = pesagem_service.registrar(
            farm_id=uid,
            peso=peso,
            data_pesagem=str(data_p),
            registrado_por=current_user.id,
            animal_id=aid,
            brinco=brinco,
        )
        if erro:
            erros.append(erro)
        else:
            registrados.append(alvo_id)

    if not registrados:
        msg = erros[0] if erros else 'Não foi possível registrar a pesagem.'
        return jsonify({'error': msg, 'erros': erros}), 400

    return jsonify({
        'ok': True,
        'registrados': len(registrados),
        'animal_ids': registrados,
        'erros': erros,
    }), 201


@api_bp.route('/api/medicacoes', methods=['POST'])
@login_required
@limiter.limit("60 per minute")
def registrar_medicacoes():
    uid = current_user.farm_id
    dados = _payload_json()

    nome = (dados.get('nome_medicamento') or dados.get('nome') or '').strip()
    if not nome:
        return jsonify({'error': 'Nome do medicamento é obrigatório'}), 400

    data_aplicacao = (
        dados.get('data_aplicacao')
        or dados.get('data')
        or date.today().isoformat()
    )
    try:
        custo = float(dados.get('custo') or 0.0)
    except (TypeError, ValueError):
        return jsonify({'error': 'Custo inválido'}), 400

    obs = (dados.get('observacoes') or dados.get('obs') or '').strip()

    raw_carencia = dados.get('dias_carencia')
    if raw_carencia is None or str(raw_carencia).strip() == '':
        dias_carencia = dias_carencia_sugerido(nome)
    else:
        try:
            dias_carencia = max(0, int(raw_carencia))
        except (TypeError, ValueError):
            return jsonify({'error': 'Dias de carência inválido'}), 400

    ids = []
    if isinstance(dados.get('animal_ids'), list):
        for raw_id in dados['animal_ids']:
            try:
                ids.append(int(raw_id))
            except (TypeError, ValueError):
                continue
    elif dados.get('animal_id') not in (None, ''):
        try:
            ids.append(int(dados['animal_id']))
        except (TypeError, ValueError):
            return jsonify({'error': 'animal_id inválido'}), 400

    if isinstance(dados.get('brincos'), list):
        for b in dados['brincos']:
            aid = animal_repository.get_animal_id_by_brinco(str(b).strip(), uid)
            if aid:
                ids.append(aid)
    elif dados.get('brinco'):
        aid = animal_repository.get_animal_id_by_brinco(str(dados['brinco']).strip(), uid)
        if aid:
            ids.append(aid)

    if not ids:
        return jsonify({'error': 'Nenhum animal válido informado'}), 400

    if len(ids) == 1:
        ok = animal_repository.registrar_medicacao(
            ids[0], uid, data_aplicacao, nome, custo, obs,
            dias_carencia=dias_carencia, registrado_por=current_user.id,
        )
        if not ok:
            return jsonify({'error': 'Animal não encontrado'}), 404
    else:
        animal_repository.insert_medicacao_lote(
            ids, data_aplicacao, nome, custo, obs, uid,
            dias_carencia=dias_carencia, registrado_por=current_user.id,
        )

    return jsonify({
        'ok': True,
        'dias_carencia': dias_carencia,
        'animal_ids': ids,
    }), 201


@api_bp.route('/api/vendas', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def registrar_vendas():
    uid = current_user.farm_id
    dados = _payload_json()
    data_venda = (
        dados.get('data_venda')
        or dados.get('data')
        or date.today().isoformat()
    )
    confirmar_carencia = dados.get('confirmar_carencia') in (
        True, 1, '1', 'true', 'True', 'sim', 'on',
    )

    vendas_input = dados.get('vendas')
    if not isinstance(vendas_input, list):
        vendas_input = [dados]

    vendas_resolvidas = []
    for item in vendas_input:
        if not isinstance(item, dict):
            continue
        aid = item.get('animal_id') or item.get('id')
        if aid not in (None, ''):
            try:
                aid = int(aid)
            except (TypeError, ValueError):
                return jsonify({'error': 'animal_id inválido'}), 400
        elif item.get('brinco'):
            aid = animal_repository.get_animal_id_by_brinco(str(item['brinco']).strip(), uid)
            if not aid:
                return jsonify({'error': f"Brinco '{item['brinco']}' não encontrado"}), 404
        else:
            continue

        try:
            peso_v = float(item.get('peso_venda') if item.get('peso_venda') is not None else item.get('peso'))
            preco_v = float(item.get('preco_venda') if item.get('preco_venda') is not None else item.get('preco'))
        except (TypeError, ValueError):
            return jsonify({'error': 'Peso e preço de venda são obrigatórios e devem ser numéricos'}), 400

        if peso_v <= 0 or preco_v < 0:
            return jsonify({'error': 'Peso e preço de venda devem ser positivos'}), 400

        vendas_resolvidas.append((aid, peso_v, preco_v))

    if not vendas_resolvidas:
        return jsonify({'error': 'Nenhum animal informado para venda'}), 400

    animal_ids = [v[0] for v in vendas_resolvidas]
    carencias_ativas = sanitario_repository.get_carencias_ativas(uid, animal_ids)

    if carencias_ativas and not confirmar_carencia:
        return jsonify({
            'error': 'Animais em carência sanitária',
            'carencias': [_formatar_carencia(c) for c in carencias_ativas],
        }), 400

    if len(vendas_resolvidas) == 1:
        aid, peso_v, preco_v = vendas_resolvidas[0]
        ok = animal_repository.registrar_venda(
            aid, uid, data_venda, preco_v, peso_v, registrado_por=current_user.id,
        )
        if not ok:
            return jsonify({'error': 'Animal não encontrado'}), 404
        vendidos = 1
        invalidos = []
    else:
        vendidos, invalidos = animal_repository.registrar_venda_lote(
            vendas_resolvidas, uid, data_venda, registrado_por=current_user.id,
        )
        if vendidos == 0:
            return jsonify({'error': 'Nenhum animal válido para venda', 'invalidos': invalidos}), 400

    if carencias_ativas and confirmar_carencia:
        fn_override = getattr(
            sanitario_repository,
            'registrar_venda_com_carencia',
            sanitario_repository.registrar_override_carencia,
        )
        fn_override(carencias_ativas, current_user.id)

    return jsonify({
        'ok': True,
        'vendidos': vendidos,
        'invalidos': invalidos,
        'carencia_override': bool(carencias_ativas and confirmar_carencia),
    })


# ══════════════════════════════════════════════════════════════════════════════
# GRÁFICOS E EXPORTAÇÕES (EXISTENTES)
# ══════════════════════════════════════════════════════════════════════════════

@api_bp.route('/api/graficos/sexo')
@login_required
@limiter.limit("60 per minute")
def graficos_sexo():
    rows = animal_repository.get_contagem_por_sexo(current_user.farm_id)
    return _with_cache(jsonify({sexo: qtd for sexo, qtd in rows}))

@api_bp.route('/api/graficos/peso')
@login_required
@limiter.limit("60 per minute")
def graficos_peso():
    rows = animal_repository.get_pesos_atuais_rebanho(current_user.farm_id)
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
    gmd_medio = animal_repository.get_gmd_medio_rebanho(current_user.farm_id, sexo=sexo)
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
    resultado = animal_repository.get_gmd_lote(animal_ids, current_user.farm_id)
    return jsonify(resultado)


@api_bp.route('/api/dashboard-summary')
@login_required
@limiter.limit("60 per minute")
def dashboard_summary():
    """Retorna sexo + GMD + alertas em uma única request — 2 queries vs 3 antes."""
    uid = current_user.farm_id
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

@api_bp.route('/api/v1/export/animais.csv')
@login_required
@limiter.limit("10 per minute")
def export_animais_csv():
    # get_animais_com_gmd: id(0) brinco(1) sexo(2) raca(3) data_compra(4) gmd(5) dias(6) peso_final(7)
    rows = animal_repository.get_animais_com_gmd(current_user.farm_id)
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


# ══════════════════════════════════════════════════════════════════════════════
# FINANCEIRO
# ══════════════════════════════════════════════════════════════════════════════

@api_bp.route('/api/financeiro/resumo', methods=['GET'])
@login_required
@limiter.limit("60 per minute")
def financeiro_resumo():
    uid = current_user.farm_id
    ano = request.args.get('ano', date.today().year, type=int)
    fluxo_rows = financeiro_repository.get_fluxo_caixa(uid)
    valor_rebanho = financeiro_repository.get_valor_rebanho(uid)
    categorias_rows = financeiro_repository.get_categorias_custo()

    anos_lista = []
    resumo_ano = {
        'ano': ano,
        'total_entradas': 0.0,
        'total_compras': 0.0,
        'total_med': 0.0,
        'total_ops': 0.0,
        'total_saidas': 0.0,
        'saldo': 0.0,
    }

    for r in fluxo_rows:
        r_ano = int(r[0]) if r[0] is not None else ano
        entradas = float(r[1] or 0.0)
        compras = float(r[2] or 0.0)
        med = float(r[3] or 0.0)
        ops = float(r[4] or 0.0)
        saidas = compras + med + ops
        item = {
            'ano': r_ano,
            'total_entradas': entradas,
            'total_compras': compras,
            'total_med': med,
            'total_ops': ops,
            'total_saidas': saidas,
            'saldo': entradas - saidas,
        }
        anos_lista.append(item)
        if r_ano == ano:
            resumo_ano = item

    # Breakdown mensal (1..12) para o ano selecionado
    meses_map = {m: {'mes': m, 'entradas': 0.0, 'saidas': 0.0, 'compras': 0.0, 'medicacoes': 0.0, 'operacional': 0.0} for m in range(1, 13)}
    inicio = date(ano, 1, 1)
    fim = date(ano, 12, 31)
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT EXTRACT(MONTH FROM data_venda)::int, COALESCE(SUM(preco_venda), 0) "
            "FROM animais WHERE user_id = %s AND deleted_at IS NULL "
            "AND data_venda >= %s AND data_venda <= %s GROUP BY 1",
            (uid, inicio, fim),
        )
        for m, val in cursor.fetchall():
            if int(m) in meses_map:
                meses_map[int(m)]['entradas'] += float(val or 0.0)

        cursor.execute(
            "SELECT EXTRACT(MONTH FROM data_compra)::int, COALESCE(SUM(preco_compra), 0) "
            "FROM animais WHERE user_id = %s AND deleted_at IS NULL "
            "AND data_compra >= %s AND data_compra <= %s GROUP BY 1",
            (uid, inicio, fim),
        )
        for m, val in cursor.fetchall():
            if int(m) in meses_map:
                v = float(val or 0.0)
                meses_map[int(m)]['compras'] += v
                meses_map[int(m)]['saidas'] += v

        cursor.execute(
            "SELECT EXTRACT(MONTH FROM m.data_aplicacao)::int, COALESCE(SUM(m.custo), 0) "
            "FROM medicacoes m JOIN animais a ON m.animal_id = a.id "
            "WHERE a.user_id = %s AND m.deleted_at IS NULL AND a.deleted_at IS NULL "
            "AND m.data_aplicacao >= %s AND m.data_aplicacao <= %s GROUP BY 1",
            (uid, inicio, fim),
        )
        for m, val in cursor.fetchall():
            if int(m) in meses_map:
                v = float(val or 0.0)
                meses_map[int(m)]['medicacoes'] += v
                meses_map[int(m)]['saidas'] += v

        cursor.execute(
            "SELECT EXTRACT(MONTH FROM data_custo)::int, COALESCE(SUM(valor), 0) "
            "FROM custos_operacionais WHERE user_id = %s AND deleted_at IS NULL "
            "AND data_custo >= %s AND data_custo <= %s GROUP BY 1",
            (uid, inicio, fim),
        )
        for m, val in cursor.fetchall():
            if int(m) in meses_map:
                v = float(val or 0.0)
                meses_map[int(m)]['operacional'] += v
                meses_map[int(m)]['saidas'] += v

    return jsonify({
        'ano': ano,
        'valor_rebanho': valor_rebanho,
        'resumo': resumo_ano,
        'historico_anual': anos_lista,
        'meses': [meses_map[m] for m in range(1, 13)],
        'categorias': [{'nome': c[0], 'categoria': c[1]} for c in categorias_rows],
    })


@api_bp.route('/api/financeiro/resultado-lotes', methods=['GET'])
@login_required
@limiter.limit("60 per minute")
def financeiro_resultado_lotes():
    rows = financeiro_repository.get_resultado_lotes(current_user.farm_id)
    return jsonify([
        {
            'lote_id': r[0],
            'codigo_lote': r[1],
            'descricao': r[2] or '',
            'data_aquisicao': _iso(r[3]),
            'total_animais': int(r[4] or 0),
            'custo_aquisicao': float(r[5] or 0.0),
            'receita_vendas': float(r[6] or 0.0),
            'custo_medicacoes': float(r[7] or 0.0),
            'animais_vendidos': int(r[8] or 0),
            'margem_bruta': float(r[9] or 0.0),
        }
        for r in rows
    ])


@api_bp.route('/api/financeiro/custos', methods=['GET'])
@login_required
@limiter.limit("60 per minute")
def custos_por_ano():
    """Retorna detalhamento de custos do ano em JSON — usado pelo lazy-load do financeiro."""
    ano = request.args.get('ano', date.today().year, type=int)
    rows = financeiro_repository.get_custos_por_ano(current_user.farm_id, ano)
    return jsonify([{
        'data':      r[0].strftime('%d/%m/%Y') if r[0] else '',
        'data_iso':  _iso(r[0]),
        'categoria': r[1] or '',
        'descricao': r[2] or '',
        'valor':     float(r[3]) if r[3] is not None else 0.0,
        'qtd':       int(r[4]) if r[4] is not None else 1,
        'obs':       r[5] or '',
    } for r in rows])


@api_bp.route('/api/financeiro/custos', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def criar_custo():
    dados = _payload_json()
    categoria = (dados.get('categoria') or 'Variavel').strip()
    tipo_custo = (dados.get('tipo_custo') or dados.get('tipo') or '').strip()
    descricao = (dados.get('descricao') or dados.get('obs') or '').strip()
    data_custo = dados.get('data_custo') or dados.get('data') or date.today().isoformat()
    try:
        valor = float(dados.get('valor'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Valor inválido'}), 400

    if not tipo_custo or valor <= 0:
        return jsonify({'error': 'Tipo de custo e valor positivo são obrigatórios'}), 400

    financeiro_repository.insert_custo_operacional(
        current_user.farm_id,
        categoria,
        tipo_custo,
        valor,
        data_custo,
        descricao,
        registrado_por=current_user.id,
    )
    return jsonify({'ok': True}), 201


@api_bp.route('/api/financeiro/agendamentos', methods=['GET'])
@login_required
@limiter.limit("60 per minute")
def listar_agendamentos():
    rows = financeiro_repository.get_agendamentos(current_user.farm_id)
    return jsonify([
        {
            'id': r[0],
            'descricao': r[1],
            'valor': float(r[2]) if r[2] is not None else 0.0,
            'vencimento': _iso(r[3]),
            'status': r[4],
        }
        for r in rows
    ])


@api_bp.route('/api/financeiro/agendamentos', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def criar_agendamento():
    dados = _payload_json()
    acao = dados.get('acao')
    if acao == 'baixar' and dados.get('id'):
        ok = financeiro_repository.baixar_agendamento(
            int(dados['id']), current_user.farm_id, registrado_por=current_user.id
        )
        if not ok:
            return jsonify({'error': 'Agendamento não encontrado ou já pago'}), 404
        return jsonify({'ok': True})
    if acao == 'excluir' and dados.get('id'):
        ok = financeiro_repository.delete_agendamento(int(dados['id']), current_user.farm_id)
        if not ok:
            return jsonify({'error': 'Agendamento não encontrado'}), 404
        return jsonify({'ok': True})

    descricao = (dados.get('descricao') or '').strip()
    vencimento = dados.get('vencimento') or date.today().isoformat()
    try:
        valor = float(dados.get('valor'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Valor inválido'}), 400

    if not descricao or valor <= 0:
        return jsonify({'error': 'Descrição e valor positivo são obrigatórios'}), 400

    financeiro_repository.insert_agendamento(
        current_user.farm_id, descricao, valor, vencimento
    )
    return jsonify({'ok': True}), 201


@api_bp.route('/api/v1/export/financeiro.csv')
@login_required
@limiter.limit("10 per minute")
def export_financeiro_csv():
    ano = request.args.get('ano', date.today().year, type=int)
    rows = financeiro_repository.get_custos_por_ano(current_user.farm_id, ano)
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
    rows = animal_repository.get_animais_abaixo_gmd_medio(current_user.farm_id)
    if not rows:
        gmd_media = animal_repository.get_gmd_medio_rebanho(current_user.farm_id)
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


# ══════════════════════════════════════════════════════════════════════════════
# PASTOS, SANIDADE, ESTOQUE E REPRODUÇÃO
# ══════════════════════════════════════════════════════════════════════════════

@api_bp.route('/api/pastos', methods=['GET'])
@login_required
@limiter.limit("60 per minute")
def listar_pastos():
    uid = current_user.farm_id
    pastos_rows = pasto_repository.get_pastos(uid)
    gmd_rows = pasto_repository.get_gmd_por_modulo(uid)
    gmd_por_modulo = {
        r[0]: {
            'modulo_id': r[0],
            'modulo_nome': r[1],
            'pasto_id': r[2],
            'qtd_animais': int(r[3] or 0),
            'gmd_medio': round(float(r[4]), 3) if r[4] is not None else None,
        }
        for r in gmd_rows
    }

    pastos_lista = []
    for p in pastos_rows:
        pid = p[0]
        modulos_rows = pasto_repository.get_modulos_by_pasto(pid, uid)
        animais_ativos = pasto_repository.get_animais_ocupacoes_ativas(pid, uid)
        animais_por_oc = {}
        for oc_id, aid, brinco in animais_ativos:
            animais_por_oc.setdefault(oc_id, []).append({'id': aid, 'brinco': brinco})

        modulos_lista = []
        for m in modulos_rows:
            mid = m[0]
            area_ha = float(m[2]) if m[2] is not None else 0.0
            cap_ua = float(m[3]) if m[3] is not None else 0.0
            ua_atual = int(m[4] or 0)
            pct_lotacao = float(m[5]) if m[5] is not None else 0.0
            oc_id = m[6]
            gmd_info = gmd_por_modulo.get(mid, {})
            modulos_lista.append({
                'id': mid,
                'pasto_id': pid,
                'nome': m[1],
                'area_hectares': area_ha,
                'capacidade_ua': cap_ua,
                'ua_atual': ua_atual,
                'ua_ha': round(ua_atual / area_ha, 2) if area_ha > 0 else 0.0,
                'pct_lotacao': pct_lotacao,
                'ocupacao_id': oc_id,
                'data_entrada': _iso(m[7]),
                'dias_descanso': int(m[8]) if m[8] is not None else None,
                'ultima_saida': _iso(m[9]),
                'gmd_medio': gmd_info.get('gmd_medio'),
                'animais': animais_por_oc.get(oc_id, []) if oc_id else [],
            })

        pastos_lista.append({
            'id': pid,
            'nome': p[1],
            'area_hectares': float(p[2]) if p[2] is not None else 0.0,
            'forrageira': p[3] or '',
            'capacidade_ua': float(p[4]) if p[4] is not None else 0.0,
            'qtd_modulos': int(p[5] or 0),
            'superlotados': int(p[6] or 0),
            'em_alerta': int(p[7] or 0),
            'modulos': modulos_lista,
        })

    return jsonify({
        'pastos': pastos_lista,
        'gmd_por_modulo': list(gmd_por_modulo.values()),
    })


@api_bp.route('/api/sanitario/protocolos', methods=['GET'])
@login_required
@limiter.limit("60 per minute")
def listar_protocolos():
    uid = current_user.farm_id
    rows = sanitario_repository.get_protocolos(uid)
    vencendo_rows = sanitario_repository.get_vencendo_em_dias(uid, dias=7)
    hoje = date.today()

    protocolos = []
    for r in rows:
        prox = r[4]
        dias_rest = (prox - hoje).days if isinstance(prox, date) else None
        protocolos.append({
            'id': r[0],
            'nome': r[1],
            'descricao': r[2] or '',
            'intervalo_dias': int(r[3] or 0),
            'proxima_aplicacao': _iso(prox),
            'dias_restantes': dias_rest,
            'vencido': dias_rest is not None and dias_rest < 0,
            'vencendo': dias_rest is not None and 0 <= dias_rest <= 7,
            'ativo': bool(r[5]),
        })

    vencendo = [
        {
            'id': v[0],
            'nome': v[1],
            'proxima_aplicacao': _iso(v[2]),
            'intervalo_dias': int(v[3] or 0),
        }
        for v in vencendo_rows
    ]
    return jsonify({'protocolos': protocolos, 'vencendo': vencendo})


@api_bp.route('/api/sanitario/carencias', methods=['GET'])
@login_required
@limiter.limit("60 per minute")
def listar_carencias():
    uid = current_user.farm_id
    rows = sanitario_repository.get_carencias_ativas(uid)
    medicamento_q = request.args.get('medicamento', '').strip()
    return jsonify({
        'carencias': [_formatar_carencia(c) for c in rows],
        'sugestao_dias': dias_carencia_sugerido(medicamento_q) if medicamento_q else 0,
        'padroes': CARENCIA_PADRAO,
    })


@api_bp.route('/api/estoque', methods=['GET'])
@login_required
@limiter.limit("60 per minute")
def listar_estoque():
    uid = current_user.farm_id
    termo = request.args.get('termo', '').strip() or None
    rows = estoque_repository.get_produtos(uid, termo=termo)
    vencendo_rows = estoque_repository.get_vencendo_em_dias(uid, dias=30)

    produtos = [
        {
            'id': r[0],
            'nome': r[2],
            'unidade': r[3],
            'categoria': r[4],
            'estoque_minimo': float(r[5] or 0.0),
            'total_entradas': float(r[6] or 0.0),
            'total_saidas': float(r[7] or 0.0),
            'saldo_atual': float(r[8] or 0.0),
            'abaixo_minimo': bool(r[9]),
            'proxima_validade': _iso(r[10]),
            'tem_vencido': bool(r[11]),
        }
        for r in rows
    ]

    movimentacoes = []
    produto_id = request.args.get('produto_id', type=int)
    if produto_id:
        mov_rows = estoque_repository.get_movimentacoes_by_produto(produto_id, uid)
        movimentacoes = [
            {
                'id': m[0],
                'tipo': m[1],
                'quantidade': float(m[2] or 0.0),
                'custo_unitario': float(m[3]) if m[3] is not None else None,
                'motivo': m[4] or '',
                'data_mov': _iso(m[5]),
                'lote_fabricante': m[6] or '',
                'data_validade': _iso(m[7]),
            }
            for m in mov_rows
        ]

    return jsonify({
        'produtos': produtos,
        'vencendo': [
            {
                'produto_id': v[0],
                'nome': v[1],
                'proxima_validade': _iso(v[2]),
                'tem_vencido': bool(v[3]),
            }
            for v in vencendo_rows
        ],
        'movimentacoes': movimentacoes,
    })


@api_bp.route('/api/reproducao', methods=['GET'])
@login_required
@limiter.limit("60 per minute")
def listar_reproducao():
    uid = current_user.farm_id
    gestantes = reproducao_repository.get_contagem_gestantes(uid)
    partos_rows = reproducao_repository.get_partos_previstos(uid, dias=365)
    ranking_rows = animal_repository.get_ranking_touros(uid)

    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT r.id, r.vaca_id, v.brinco AS vaca_brinco, "
            "       r.touro_id, t.brinco AS touro_brinco, r.touro_externo, "
            "       r.data_cobertura, r.diagnostico, r.data_diagnostico, "
            "       r.data_parto_prevista, r.data_parto, r.resultado "
            "FROM reproducao r "
            "JOIN animais v ON r.vaca_id = v.id "
            "LEFT JOIN animais t ON r.touro_id = t.id "
            "WHERE r.user_id = %s AND v.deleted_at IS NULL "
            "ORDER BY r.data_cobertura DESC LIMIT 200",
            (uid,),
        )
        rep_rows = cursor.fetchall()

    return jsonify({
        'gestantes': gestantes,
        'partos_previstos': [
            {
                'id': p[0],
                'vaca_brinco': p[1],
                'data_cobertura': _iso(p[2]),
                'data_parto_prevista': _iso(p[3]),
                'dias_restantes': int(p[4]) if p[4] is not None else None,
                'vaca_id': p[5],
            }
            for p in partos_rows
        ],
        'ranking_touros': [
            {
                'touro_id': t[0],
                'touro_brinco': t[1],
                'touro_raca': t[2] or '',
                'qtd_filhos': int(t[3] or 0),
                'gmd_medio_filhos': round(float(t[4]), 3) if t[4] is not None else None,
            }
            for t in ranking_rows
        ],
        'registros': [
            {
                'id': r[0],
                'vaca_id': r[1],
                'vaca_brinco': r[2],
                'touro_id': r[3],
                'touro_brinco': r[4],
                'touro_externo': r[5] or '',
                'data_cobertura': _iso(r[6]),
                'diagnostico': r[7],
                'data_diagnostico': _iso(r[8]),
                'data_parto_prevista': _iso(r[9]),
                'data_parto': _iso(r[10]),
                'resultado': r[11],
            }
            for r in rep_rows
        ],
    })


# ══════════════════════════════════════════════════════════════════════════════
# GOVERNANÇA (CONFIGURAÇÕES, ACESSOS E PLANO)
# ══════════════════════════════════════════════════════════════════════════════

@api_bp.route('/api/configuracoes', methods=['GET'])
@login_required
def obter_configuracoes():
    cfg = configuracao_repository.get_configuracao(current_user.farm_id)
    return jsonify({
        'nome_fazenda': cfg[0] if cfg and cfg[0] else '',
        'cidade_estado': cfg[1] if cfg and cfg[1] else '',
        'area_total': float(cfg[2]) if cfg and cfg[2] is not None else 0.0,
        'gmd_meta': float(cfg[3]) if cfg and cfg[3] is not None else 0.8,
    })


@api_bp.route('/api/configuracoes', methods=['PUT'])
@login_required
def salvar_configuracoes():
    dados = _payload_json()
    nome_fazenda = (dados.get('nome_fazenda') or '').strip()
    cidade_estado = (dados.get('cidade_estado') or '').strip()
    try:
        area_total = float(dados.get('area_total') or 0.0)
        gmd_meta = float(dados.get('gmd_meta') if dados.get('gmd_meta') is not None else 0.8)
    except (TypeError, ValueError):
        return jsonify({'error': 'Área total e meta de GMD devem ser numéricas'}), 400

    if not nome_fazenda:
        return jsonify({'error': 'Nome da fazenda é obrigatório'}), 400
    if gmd_meta <= 0 or gmd_meta > 5:
        return jsonify({'error': 'Meta de GMD deve estar entre 0,05 e 5,00 kg/dia'}), 400

    configuracao_repository.upsert_configuracao(
        current_user.farm_id, nome_fazenda, cidade_estado, area_total, gmd_meta
    )
    return jsonify({
        'ok': True,
        'nome_fazenda': nome_fazenda,
        'cidade_estado': cidade_estado,
        'area_total': area_total,
        'gmd_meta': gmd_meta,
    })


@api_bp.route('/api/acessos', methods=['GET'])
@login_required
def listar_acessos():
    rows = acesso_repository.listar_por_fazenda(current_user.farm_id, incluir_revogados=True)
    return jsonify({
        'acessos': [
            {
                'id': r[0],
                'account_user_id': r[1],
                'username': r[2],
                'email': r[3],
                'papel': r[4],
                'ativo': bool(r[5]),
                'created_at': _iso(r[6]),
            }
            for r in rows
        ],
        'papeis_disponiveis': list(acesso_repository.PAPEIS_CONVIDAVEIS),
    })


@api_bp.route('/api/acessos', methods=['POST'])
@login_required
def criar_acesso():
    uid = current_user.farm_id
    dados = _payload_json()
    email = (dados.get('email') or '').strip().lower()
    papel = (dados.get('papel') or '').strip().lower()

    if not email or '@' not in email:
        return jsonify({'error': 'Informe um e-mail válido'}), 400
    if papel not in acesso_repository.PAPEIS_CONVIDAVEIS:
        return jsonify({'error': f"Papel inválido. Escolha entre: {', '.join(acesso_repository.PAPEIS_CONVIDAVEIS)}"}), 400

    existente = auth_repository.get_user_by_email(email)
    if existente:
        account_user_id = existente[0]
        username = existente[1]
        if account_user_id == uid:
            return jsonify({'error': 'Você já é o proprietário desta fazenda'}), 400
    else:
        cfg = configuracao_repository.get_configuracao(uid)
        nome_fazenda = cfg[0] if cfg and cfg[0] else current_user.username
        username = acesso_repository.gerar_username(nome_fazenda, email)
        senha_inicial = generate_password_hash(secrets.token_urlsafe(24))
        account_user_id = acesso_repository.criar_convidado(username, email, senha_inicial)

    acesso_id = acesso_repository.conceder(account_user_id, uid, papel)
    return jsonify({
        'ok': True,
        'id': acesso_id,
        'account_user_id': account_user_id,
        'username': username,
        'email': email,
        'papel': papel,
        'ativo': True,
    }), 201


@api_bp.route('/api/acessos/<int:acesso_id>', methods=['DELETE'])
@login_required
def revogar_acesso(acesso_id: int):
    ok = acesso_repository.revogar(acesso_id, current_user.farm_id)
    if not ok:
        return jsonify({'error': 'Acesso não encontrado'}), 404
    return jsonify({'ok': True, 'id': acesso_id})


@api_bp.route('/api/plano', methods=['GET'])
@login_required
def obter_plano():
    return jsonify(_serializar_plano(current_user.farm_id))


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRAÇÕES EXTERNAS (IBGE E COTAÇÕES)
# ══════════════════════════════════════════════════════════════════════════════

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
    res = configuracao_repository.get_configuracao(current_user.farm_id)
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
