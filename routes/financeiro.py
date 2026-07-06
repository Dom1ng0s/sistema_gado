from flask import Blueprint, render_template, request, url_for, redirect, flash
from flask_login import login_required, current_user
import math
from datetime import date, timedelta
import logging
from repositories import animal_repository, financeiro_repository, reproducao_repository, pasto_repository
from routes.validators import validate
from utils.calculo import KG_POR_ARROBA

financeiro_bp = Blueprint('financeiro', __name__)
logger = logging.getLogger(__name__)


def calcular_kpis_unificados(user_id):
    dados = {
        'qtd_animais': 0, 'gmd_medio': 0.0, 'custo_mensal_total': 0.0,
        'custo_diaria': 0.0, 'custo_arroba': 0.0, 'dias_para_arroba': 0,
        'arrendamento': 0.0, 'suplementacao': 0.0, 'mao_obra': 0.0, 'extras': 0.0
    }

    dados['qtd_animais'] = animal_repository.count_animais(user_id, status='ativos')
    dados['gmd_medio'] = animal_repository.get_gmd_medio_rebanho(user_id)

    dt_lim = date.today() - timedelta(days=365)
    custos = financeiro_repository.get_custos_por_tipo_trimestre(user_id, dt_lim)

    tot_anual = 0.0
    for tipo, val in custos:
        v = float(val)
        tot_anual += v
        if tipo == 'Arrendamento':
            dados['arrendamento'] += v
        elif tipo == 'Nutrição':
            dados['suplementacao'] += v
        elif tipo == 'Salário':
            dados['mao_obra'] += v
        else:
            dados['extras'] += v
    dados['custo_mensal_total'] = tot_anual

    if dados['qtd_animais'] > 0:
        dados['custo_diaria'] = (tot_anual / dados['qtd_animais']) / 365
    if dados['gmd_medio'] > 0:
        dados['dias_para_arroba'] = KG_POR_ARROBA / dados['gmd_medio']
        dados['custo_arroba'] = dados['custo_diaria'] * dados['dias_para_arroba']

    return dados


@financeiro_bp.route('/financeiro')
@login_required
def financeiro():
    ano_sel = request.args.get('ano', default=date.today().year, type=int)
    view_data = {
        'valor_rebanho': 0, 'saldo_total_operacao': 0, 'classe_saldo': 'bg-verde',
        'custo_diaria': "---", 'custo_arroba': "---",
        'entradas_ano': 0, 'saidas_ano': 0, 'reposicao_ano': 0,
        'custos_op_ano': 0, 'med_ano': 0, 'balanco_ano': 0,
    }
    anos = [date.today().year]

    try:
        uid = current_user.id

        valor_reb = financeiro_repository.get_valor_rebanho(uid)
        if valor_reb:
            view_data['valor_rebanho'] = f"{valor_reb:,.2f}"

        hist = financeiro_repository.get_fluxo_caixa(uid)
        if hist:
            anos = [row[0] for row in hist]
            sal = sum(r[1] for r in hist) - sum(r[2] + r[3] + r[4] for r in hist)
            view_data['saldo_total_operacao'] = f"{sal:,.2f}"
            view_data['classe_saldo'] = 'bg-verde' if sal >= 0 else 'bg-vermelho'
            d_ano = next((r for r in hist if r[0] == ano_sel), None)
            if d_ano:
                view_data['entradas_ano'], view_data['reposicao_ano'], view_data['med_ano'], view_data['custos_op_ano'] = [
                    f"{x:,.2f}" for x in d_ano[1:]
                ]
                view_data['saidas_ano'] = f"{(d_ano[2] + d_ano[3] + d_ano[4]):,.2f}"
                view_data['balanco_ano'] = f"{(d_ano[1] - (d_ano[2] + d_ano[3] + d_ano[4])):,.2f}"

        kpis = calcular_kpis_unificados(uid)
        if kpis['custo_arroba'] > 0:
            view_data['custo_diaria'] = f"{kpis['custo_diaria']:.2f}"
            view_data['custo_arroba'] = f"{kpis['custo_arroba']:.2f}"

    except Exception as e:
        logger.error(f"Erro financeiro: {e}", exc_info=True)

    PER_PAGE = 20
    page = request.args.get('page', 1, type=int)
    custos = []
    total_custos = 0
    total_paginas = 1
    try:
        total_custos = financeiro_repository.count_custos_por_ano(current_user.id, ano_sel)
        total_paginas = max(1, math.ceil(total_custos / PER_PAGE))
        page = max(1, min(page, total_paginas))
        offset = (page - 1) * PER_PAGE
        custos = financeiro_repository.get_custos_por_ano_paginado(current_user.id, ano_sel, PER_PAGE, offset)
    except Exception as e:
        logger.error(f"Erro ao carregar custos: {e}", exc_info=True)

    partos_previstos = []
    total_gestantes = 0
    try:
        partos_previstos = reproducao_repository.get_partos_previstos(current_user.id, dias=30)
        total_gestantes = reproducao_repository.get_contagem_gestantes(current_user.id)
    except Exception as e:
        logger.error(f"Erro ao carregar dados de prenhez: {e}", exc_info=True)

    top_gmd_modulos = []
    try:
        top_gmd_modulos = pasto_repository.get_top_gmd_por_modulo(current_user.id)
    except Exception as e:
        logger.error(f"Erro ao carregar GMD por módulo: {e}", exc_info=True)

    return render_template('financeiro.html', financeiro=view_data, ano_selecionado=ano_sel, anos=anos,
                           custos=custos, pagina_atual=page, total_custos=total_custos, total_paginas=total_paginas,
                           partos_previstos=partos_previstos, total_gestantes=total_gestantes,
                           top_gmd_modulos=top_gmd_modulos)


@financeiro_bp.route('/simulador-custo', methods=['GET', 'POST'])
@login_required
def simulador_custo():
    res = None
    sugestoes = {
        'qtd_animais': 0, 'gmd_medio': 0.0,
        'arrendamento': 0.0, 'suplementacao': 0.0, 'mao_obra': 0.0, 'extras': 0.0,
    }

    try:
        if request.method == 'GET':
            sugestoes = calcular_kpis_unificados(current_user.id)
    except Exception as e:
        logger.error(f"Erro simulador: {e}", exc_info=True)

    if request.method == 'POST':
        errors = validate(request.form, [
            ('qtd_animais',        {'required': True, 'type': 'int',   'min_val': 1,    'max_val': 99999, 'label': 'Qtd. animais'}),
            ('gmd',                {'required': True, 'type': 'float', 'min_val': 0,    'max_val': 10,    'label': 'GMD'}),
            ('custo_arrendamento', {'required': True, 'type': 'float', 'min_val': 0,                      'label': 'Custo arrendamento'}),
            ('custo_suplementacao',{'required': True, 'type': 'float', 'min_val': 0,                      'label': 'Custo suplementação'}),
            ('custo_mao_obra',     {'required': True, 'type': 'float', 'min_val': 0,                      'label': 'Custo mão de obra'}),
            ('custos_extras',      {'required': True, 'type': 'float', 'min_val': 0,                      'label': 'Custos extras'}),
        ])
        if errors:
            return render_template('simulador_custo.html', sugestoes=sugestoes, resultados={'erro': errors[0]}), 400

        try:
            qtd = int(request.form.get('qtd_animais', 1))
            gmd = float(request.form.get('gmd', '0').replace(',', '.'))
            c_arr = float(request.form.get('custo_arrendamento', '0').replace(',', '.'))
            c_sup = float(request.form.get('custo_suplementacao', '0').replace(',', '.'))
            c_mao = float(request.form.get('custo_mao_obra', '0').replace(',', '.'))
            c_ext = float(request.form.get('custos_extras', '0').replace(',', '.'))

            sugestoes.update({'qtd_animais': qtd, 'gmd_medio': gmd, 'arrendamento': c_arr,
                              'suplementacao': c_sup, 'mao_obra': c_mao, 'extras': c_ext})

            c_anual = c_arr + c_sup + c_mao + c_ext
            c_dia = (c_anual / qtd / 365) if qtd > 0 else 0
            d_arr = (KG_POR_ARROBA / gmd) if gmd > 0 else 0
            c_arr_val = c_dia * d_arr

            res = {
                'custo_total': f"{c_anual:,.2f}",
                'custo_diaria': f"{c_dia:,.2f}",
                'dias_arroba': int(d_arr),
                'custo_arroba': f"{c_arr_val:,.2f}",
            }
        except ValueError:
            res = {'erro': "Erro numérico."}

    return render_template('simulador_custo.html', sugestoes=sugestoes, resultados=res)


@financeiro_bp.route('/custos_operacionais', methods=['GET', 'POST'])
@login_required
def custos_operacionais():
    msg = None
    if request.method == 'POST':
        errors = validate(request.form, [
            ('categoria', {'required': True,  'choices': ['Fixo', 'Variavel'],      'label': 'Categoria'}),
            ('valor',     {'required': True,  'type': 'float', 'min_val': 0.01,     'label': 'Valor'}),
            ('data',      {'required': True,  'type': 'date',                       'label': 'Data'}),
            ('descricao', {'required': False, 'type': 'str',   'max_len': 500,      'label': 'Descrição'}),
        ])
        cat = request.form.get('categoria', '').strip()
        tipo_field = 'tipo_fixo' if cat == 'Fixo' else 'tipo_variavel'
        if not request.form.get(tipo_field, '').strip():
            errors.append("'Tipo' é obrigatório.")
        if errors:
            msg = errors[0]
        else:
            try:
                tipo = request.form.get(tipo_field)
                val = float(request.form.get('valor'))
                dt = request.form.get('data')
                desc = request.form.get('descricao')

                financeiro_repository.insert_custo_operacional(current_user.id, cat, tipo, val, dt, desc)
                flash("Custo registrado com sucesso.", 'success')
                return redirect(url_for('financeiro.custos_operacionais'))
            except Exception as e:
                logger.error(f"Erro custos: {e}", exc_info=True)
                flash(f"Erro: {e}", 'error')
                return redirect(url_for('financeiro.custos_operacionais'))

    cats_fixo, cats_variavel = [], []
    try:
        for nome, cat in financeiro_repository.get_categorias_custo():
            if cat == 'Fixo':
                cats_fixo.append(nome)
            else:
                cats_variavel.append(nome)
    except Exception as e:
        logger.error(f"Erro ao carregar categorias: {e}", exc_info=True)

    return render_template('custos_operacionais.html', mensagem=msg, fixos=cats_fixo, variaveis=cats_variavel,
                           form_data=request.form)


@financeiro_bp.route('/financeiro/agendamentos', methods=['GET', 'POST'])
@login_required
def agendamentos():
    msg = None
    hoje = date.today()

    if request.method == 'POST':
        errors = validate(request.form, [
            ('descricao',  {'required': True, 'type': 'str',   'max_len': 500, 'label': 'Descrição'}),
            ('valor',      {'required': True, 'type': 'float', 'min_val': 0.01,'label': 'Valor'}),
            ('vencimento', {'required': True, 'type': 'date',                  'label': 'Vencimento'}),
        ])
        if errors:
            msg = errors[0]
        else:
            try:
                financeiro_repository.insert_agendamento(
                    current_user.id,
                    request.form.get('descricao'),
                    float(request.form.get('valor')),
                    request.form.get('vencimento'),
                )
                flash("Agendamento salvo com sucesso!", 'success')
                return redirect(url_for('financeiro.agendamentos'))
            except Exception as e:
                logger.error(f"Erro ao agendar: {e}", exc_info=True)
                flash(f"Erro ao salvar: {e}", 'error')
                return redirect(url_for('financeiro.agendamentos'))

    contas = []
    editando = None
    try:
        contas = financeiro_repository.get_agendamentos(current_user.id)
        editar_id = request.args.get('editar', type=int)
        if editar_id:
            editando = next((c for c in contas if c[0] == editar_id and c[4] == 'pendente'), None)
    except Exception as e:
        logger.error(f"Erro lista agendamentos: {e}", exc_info=True)

    return render_template('agendamentos.html', agendamentos=contas, mensagem=msg, hoje=hoje, editando=editando,
                           form_data=request.form)


@financeiro_bp.route('/financeiro/lotes')
@login_required
def resultado_lotes():
    lotes = []
    try:
        lotes = financeiro_repository.get_resultado_lotes(current_user.id)
    except Exception as e:
        logger.error(f"Erro resultado lotes: {e}", exc_info=True)
    return render_template('resultado_lotes.html', lotes=lotes)


@financeiro_bp.route('/financeiro/lotes/<int:lote_id>')
@login_required
def detalhe_lote(lote_id):
    lote = None
    animais = []
    try:
        lote = financeiro_repository.get_resultado_lote_by_id(lote_id, current_user.id)
        if lote is None:
            return redirect(url_for('financeiro.resultado_lotes'))
        animais = financeiro_repository.get_animais_por_lote(lote_id, current_user.id)
    except Exception as e:
        logger.error(f"Erro detalhe lote: {e}", exc_info=True)
    return render_template('detalhe_lote.html', lote=lote, animais=animais)


@financeiro_bp.route('/financeiro/agendamentos/<int:id_agendamento>/editar', methods=['POST'])
@login_required
def editar_agendamento(id_agendamento):
    errors = validate(request.form, [
        ('descricao',  {'required': True, 'type': 'str',   'max_len': 500, 'label': 'Descrição'}),
        ('valor',      {'required': True, 'type': 'float', 'min_val': 0.01,'label': 'Valor'}),
        ('vencimento', {'required': True, 'type': 'date',                  'label': 'Vencimento'}),
    ])
    if errors:
        flash(errors[0], 'error')
    else:
        try:
            ok = financeiro_repository.update_agendamento(
                id_agendamento, current_user.id,
                request.form.get('descricao'),
                float(request.form.get('valor')),
                request.form.get('vencimento'),
            )
            if ok:
                flash('Agendamento atualizado com sucesso.', 'success')
            else:
                flash('Agendamento não encontrado, já pago ou sem permissão.', 'error')
        except Exception as e:
            logger.error(f"Erro editar agendamento {id_agendamento}: {e}", exc_info=True)
            flash('Erro ao atualizar agendamento.', 'error')
    return redirect(url_for('financeiro.agendamentos'))


@financeiro_bp.route('/financeiro/agendamentos/<int:id_agendamento>/excluir', methods=['POST'])
@login_required
def excluir_agendamento(id_agendamento):
    try:
        ok = financeiro_repository.delete_agendamento(id_agendamento, current_user.id)
        if ok:
            flash('Agendamento excluído.', 'success')
        else:
            flash('Agendamento não encontrado, já pago ou sem permissão.', 'error')
    except Exception as e:
        logger.error(f"Erro excluir agendamento {id_agendamento}: {e}", exc_info=True)
        flash('Erro ao excluir agendamento.', 'error')
    return redirect(url_for('financeiro.agendamentos'))


@financeiro_bp.route('/financeiro/baixar/<int:id_agendamento>', methods=['POST'])
@login_required
def baixar_agendamento(id_agendamento):
    try:
        ok = financeiro_repository.baixar_agendamento(id_agendamento, current_user.id)
        if ok:
            flash('Conta baixada com sucesso.', 'success')
        else:
            flash('Agendamento não encontrado ou já foi pago.', 'error')
    except Exception as e:
        logger.error(f"Erro ao dar baixa: {e}", exc_info=True)
        flash('Erro ao processar baixa. Tente novamente.', 'error')
    return redirect(url_for('financeiro.agendamentos'))
