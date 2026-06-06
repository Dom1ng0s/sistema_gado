from flask import Blueprint, render_template, request, url_for, redirect
from flask_login import login_required, current_user
from datetime import date, timedelta
import logging
from repositories import animal_repository, financeiro_repository

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

    dt_lim = date.today() - timedelta(days=90)
    custos = financeiro_repository.get_custos_por_tipo_trimestre(user_id, dt_lim)

    tot_tri = 0.0
    for tipo, val in custos:
        m_mensal = float(val) / 3
        tot_tri += m_mensal
        if tipo == 'Arrendamento':
            dados['arrendamento'] += m_mensal
        elif tipo == 'Nutrição':
            dados['suplementacao'] += m_mensal
        elif tipo == 'Salário':
            dados['mao_obra'] += m_mensal
        else:
            dados['extras'] += m_mensal
    dados['custo_mensal_total'] = tot_tri

    if dados['qtd_animais'] > 0:
        dados['custo_diaria'] = (tot_tri / dados['qtd_animais']) / 30
    if dados['gmd_medio'] > 0:
        dados['dias_para_arroba'] = 30 / dados['gmd_medio']
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
    anos, lista_custos = [date.today().year], []

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

        lista_custos = financeiro_repository.get_custos_por_ano(uid, ano_sel)
    except Exception as e:
        logger.error(f"Erro financeiro: {e}", exc_info=True)

    return render_template('financeiro.html', financeiro=view_data, ano_selecionado=ano_sel, anos=anos, detalhes_custos=lista_custos)


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
        try:
            qtd = int(request.form.get('qtd_animais', 1))
            gmd = float(request.form.get('gmd', '0').replace(',', '.'))
            c_arr = float(request.form.get('custo_arrendamento', '0').replace(',', '.'))
            c_sup = float(request.form.get('custo_suplementacao', '0').replace(',', '.'))
            c_mao = float(request.form.get('custo_mao_obra', '0').replace(',', '.'))
            c_ext = float(request.form.get('custos_extras', '0').replace(',', '.'))

            sugestoes.update({'qtd_animais': qtd, 'gmd_medio': gmd, 'arrendamento': c_arr,
                              'suplementacao': c_sup, 'mao_obra': c_mao, 'extras': c_ext})

            c_men = c_arr + c_sup + c_mao + c_ext
            c_dia = (c_men / qtd / 30) if qtd > 0 else 0
            d_arr = (30 / gmd) if gmd > 0 else 0
            c_arr_val = c_dia * d_arr

            res = {
                'custo_mensal_total': f"{c_men:,.2f}",
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
        try:
            cat = request.form.get('categoria')
            tipo = request.form.get('tipo_fixo') if cat == 'Fixo' else request.form.get('tipo_variavel')
            val = float(request.form.get('valor'))
            dt = request.form.get('data')
            desc = request.form.get('descricao')

            financeiro_repository.insert_custo_operacional(current_user.id, cat, tipo, val, dt, desc)
            msg = "Custo registrado com sucesso."
        except Exception as e:
            logger.error(f"Erro custos: {e}", exc_info=True)
            msg = f"Erro: {e}"

    cats_fixo, cats_variavel = [], []
    try:
        for nome, cat in financeiro_repository.get_categorias_custo():
            if cat == 'Fixo':
                cats_fixo.append(nome)
            else:
                cats_variavel.append(nome)
    except Exception as e:
        logger.error(f"Erro ao carregar categorias: {e}", exc_info=True)

    return render_template('custos_operacionais.html', mensagem=msg, fixos=cats_fixo, variaveis=cats_variavel)


@financeiro_bp.route('/financeiro/agendamentos', methods=['GET', 'POST'])
@login_required
def agendamentos():
    msg = None
    hoje = date.today()

    if request.method == 'POST':
        try:
            financeiro_repository.insert_agendamento(
                current_user.id,
                request.form.get('descricao'),
                float(request.form.get('valor')),
                request.form.get('vencimento'),
            )
            msg = "Agendamento salvo com sucesso!"
        except Exception as e:
            logger.error(f"Erro ao agendar: {e}", exc_info=True)
            msg = f"Erro ao salvar: {e}"

    contas = []
    try:
        contas = financeiro_repository.get_agendamentos(current_user.id)
    except Exception as e:
        logger.error(f"Erro lista agendamentos: {e}", exc_info=True)

    return render_template('agendamentos.html', agendamentos=contas, mensagem=msg, hoje=hoje)


@financeiro_bp.route('/financeiro/baixar/<int:id_agendamento>')
@login_required
def baixar_agendamento(id_agendamento):
    try:
        financeiro_repository.baixar_agendamento(id_agendamento, current_user.id)
    except Exception as e:
        logger.error(f"Erro ao dar baixa: {e}", exc_info=True)
    return redirect(url_for('financeiro.agendamentos'))
