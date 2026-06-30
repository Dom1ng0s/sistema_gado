from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import date
import logging
from repositories import pasto_repository, animal_repository
from routes.validators import validate

pastos_bp = Blueprint('pastos', __name__)
logger = logging.getLogger(__name__)


@pastos_bp.route('/pastos')
@login_required
def listar_pastos():
    busca = request.args.get('busca', '').strip()
    try:
        pastos = pasto_repository.get_pastos(current_user.id)
        if busca:
            bl = busca.lower()
            pastos = [p for p in pastos if bl in (p[1] or '').lower()]
    except Exception as e:
        logger.error(f"Erro ao listar pastos: {e}", exc_info=True)
        flash("Erro ao carregar pastos. Execute init_db.py para criar as views necessárias.", 'error')
        pastos = []
    return render_template('pastos_lista.html', pastos=pastos, busca=busca)


@pastos_bp.route('/pastos', methods=['POST'])
@login_required
def criar_pasto():
    erros = validate(request.form, [
        ('nome',          {'label': 'Nome', 'required': True,  'type': 'str',   'max_len': 100}),
        ('area_hectares', {'label': 'Área (ha)', 'required': False, 'type': 'float', 'min': 0}),
        ('forrageira',    {'label': 'Forrageira', 'required': False, 'type': 'str', 'max_len': 100}),
        ('capacidade_ua', {'label': 'Capacidade UA', 'required': False, 'type': 'float', 'min': 0}),
    ])
    if erros:
        flash(' | '.join(erros), 'error')
        return redirect(url_for('pastos.listar_pastos'))

    nome      = request.form.get('nome', '').strip()
    area      = request.form.get('area_hectares', '').strip() or None
    forrageira = request.form.get('forrageira', '').strip() or None
    cap_ua    = request.form.get('capacidade_ua', '').strip() or None

    pasto_repository.insert_pasto(
        current_user.id, nome,
        float(area) if area else None,
        forrageira,
        float(cap_ua) if cap_ua else None
    )
    flash('Pasto cadastrado com sucesso.', 'success')
    return redirect(url_for('pastos.listar_pastos'))


@pastos_bp.route('/pastos/<int:pasto_id>')
@login_required
def detalhe_pasto(pasto_id):
    pasto = pasto_repository.get_pasto_by_id(pasto_id, current_user.id)
    if not pasto:
        flash('Pasto não encontrado.', 'error')
        return redirect(url_for('pastos.listar_pastos'))

    modulos       = pasto_repository.get_modulos_by_pasto(pasto_id, current_user.id)
    animais_ativos = animal_repository.get_animais_ativos(current_user.id)

    animais_raw = pasto_repository.get_animais_ocupacoes_ativas(pasto_id, current_user.id)
    animais_por_ocupacao = {}
    for row in animais_raw:
        oc_id = row[0]
        if oc_id not in animais_por_ocupacao:
            animais_por_ocupacao[oc_id] = []
        animais_por_ocupacao[oc_id].append({'id': row[1], 'brinco': row[2]})

    return render_template('pasto_detalhe.html',
                           pasto=pasto,
                           modulos=modulos,
                           animais_ativos=animais_ativos,
                           animais_por_ocupacao=animais_por_ocupacao,
                           hoje=date.today().isoformat())


@pastos_bp.route('/pastos/<int:pasto_id>/modulos', methods=['POST'])
@login_required
def criar_modulo(pasto_id):
    if not pasto_repository.get_pasto_by_id(pasto_id, current_user.id):
        flash('Pasto não encontrado.', 'error')
        return redirect(url_for('pastos.listar_pastos'))

    erros = validate(request.form, [
        ('nome',          {'label': 'Nome do módulo', 'required': True,  'type': 'str',   'max_len': 100}),
        ('area_hectares', {'label': 'Área (ha)',       'required': False, 'type': 'float', 'min': 0}),
        ('capacidade_ua', {'label': 'Capacidade UA',   'required': False, 'type': 'float', 'min': 0}),
    ])
    if erros:
        flash(' | '.join(erros), 'error')
        return redirect(url_for('pastos.detalhe_pasto', pasto_id=pasto_id))

    nome   = request.form.get('nome', '').strip()
    area   = request.form.get('area_hectares', '').strip() or None
    cap_ua = request.form.get('capacidade_ua', '').strip() or None

    pasto_repository.insert_modulo(
        pasto_id, current_user.id, nome,
        float(area) if area else None,
        float(cap_ua) if cap_ua else None
    )
    flash('Módulo cadastrado com sucesso.', 'success')
    return redirect(url_for('pastos.detalhe_pasto', pasto_id=pasto_id))


@pastos_bp.route('/modulos/<int:modulo_id>/ocupar', methods=['POST'])
@login_required
def ocupar_modulo(modulo_id):
    modulo = pasto_repository.get_modulo_by_id(modulo_id, current_user.id)
    if not modulo:
        flash('Módulo não encontrado.', 'error')
        return redirect(url_for('pastos.listar_pastos'))

    pasto_id = modulo[4]

    if pasto_repository.get_ocupacao_ativa(modulo_id, current_user.id):
        flash('Módulo já possui uma ocupação ativa.', 'error')
        return redirect(url_for('pastos.detalhe_pasto', pasto_id=pasto_id))

    erros = validate(request.form, [
        ('data_entrada', {'label': 'Data de entrada', 'required': True, 'type': 'date'}),
    ])
    animal_ids = request.form.getlist('animal_ids[]')
    if not animal_ids:
        erros.append("Selecione ao menos um animal.")
    if erros:
        flash(' | '.join(erros), 'error')
        return redirect(url_for('pastos.detalhe_pasto', pasto_id=pasto_id))

    data_entrada = request.form.get('data_entrada')
    pasto_repository.iniciar_ocupacao(modulo_id, current_user.id, data_entrada, animal_ids)
    flash('Ocupação iniciada com sucesso.', 'success')
    return redirect(url_for('pastos.detalhe_pasto', pasto_id=pasto_id))


@pastos_bp.route('/ocupacoes/<int:ocupacao_id>/encerrar', methods=['POST'])
@login_required
def encerrar_ocupacao(ocupacao_id):
    pasto_id = request.form.get('pasto_id')

    erros = validate(request.form, [
        ('data_saida', {'label': 'Data de saída', 'required': True, 'type': 'date'}),
    ])
    if erros:
        flash(' | '.join(erros), 'error')
        dest = url_for('pastos.detalhe_pasto', pasto_id=int(pasto_id)) if pasto_id else url_for('pastos.listar_pastos')
        return redirect(dest)

    data_saida = request.form.get('data_saida')
    ok = pasto_repository.encerrar_ocupacao(ocupacao_id, current_user.id, data_saida)
    if not ok:
        flash('Ocupação não encontrada ou já encerrada.', 'error')
    else:
        flash('Ocupação encerrada com sucesso.', 'success')

    if pasto_id:
        return redirect(url_for('pastos.detalhe_pasto', pasto_id=int(pasto_id)))
    return redirect(url_for('pastos.listar_pastos'))


@pastos_bp.route('/pastos/gmd')
@login_required
def gmd_por_modulo():
    ranking = pasto_repository.get_gmd_por_modulo(current_user.id)
    return render_template('pastos_gmd.html', ranking=ranking)
