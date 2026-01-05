from flask import Blueprint, render_template, request, url_for,redirect
from flask_login import login_required, current_user
from db_config import get_db_cursor
from datetime import date, timedelta
import logging

financeiro_bp = Blueprint('financeiro', __name__)
logger = logging.getLogger(__name__)

def calcular_kpis_unificados(cursor, user_id):
    dados = {
        'qtd_animais': 0, 'gmd_medio': 0.0, 'custo_mensal_total': 0.0,
        'custo_diaria': 0.0, 'custo_arroba': 0.0, 'dias_para_arroba': 0,
        'arrendamento': 0.0, 'suplementacao': 0.0, 'mao_obra': 0.0, 'extras': 0.0
    }
    
    # Filtra animais deletados na contagem
    cursor.execute("SELECT COUNT(*) FROM animais WHERE user_id = %s AND data_venda IS NULL AND deleted_at IS NULL", (user_id,))
    dados['qtd_animais'] = cursor.fetchone()[0]
    
    # Filtra deletados no cálculo de GMD
    cursor.execute("SELECT AVG(v.gmd) FROM v_gmd_analitico v JOIN animais a ON v.animal_id = a.id WHERE v.user_id = %s AND a.data_venda IS NULL AND a.deleted_at IS NULL", (user_id,))
    res_gmd = cursor.fetchone()
    if res_gmd and res_gmd[0]: dados['gmd_medio'] = float(res_gmd[0])

    # Filtra custos deletados
    dt_lim = date.today() - timedelta(days=90)
    cursor.execute("SELECT tipo_custo, SUM(valor) FROM custos_operacionais WHERE user_id = %s AND data_custo >= %s AND deleted_at IS NULL GROUP BY tipo_custo", (user_id, dt_lim))
    tot_tri = 0.0
    for tipo, val in cursor.fetchall():
        m_mensal = float(val)/3
        tot_tri += m_mensal
        if tipo == 'Arrendamento': dados['arrendamento'] += m_mensal
        elif tipo == 'Nutrição': dados['suplementacao'] += m_mensal
        elif tipo == 'Salário': dados['mao_obra'] += m_mensal
        else: dados['extras'] += m_mensal
    dados['custo_mensal_total'] = tot_tri
    
    if dados['qtd_animais'] > 0: dados['custo_diaria'] = (tot_tri / dados['qtd_animais']) / 30
    if dados['gmd_medio'] > 0:
        dados['dias_para_arroba'] = 30 / dados['gmd_medio']
        dados['custo_arroba'] = dados['custo_diaria'] * dados['dias_para_arroba']
    
    return dados

@financeiro_bp.route('/financeiro')
@login_required
def financeiro():
    ano_sel = request.args.get('ano', default=date.today().year, type=int)
    view_data = {'valor_rebanho': 0, 'saldo_total_operacao': 0, 'classe_saldo': 'bg-verde', 'custo_diaria': "---", 'custo_arroba': "---", 'entradas_ano': 0, 'saidas_ano': 0, 'reposicao_ano': 0, 'custos_op_ano': 0, 'med_ano': 0, 'balanco_ano': 0}
    anos, lista_custos = [date.today().year], []

    try:
        with get_db_cursor() as cursor:
            uid = current_user.id
            
            cursor.execute("SELECT SUM(preco_compra) FROM animais WHERE data_venda IS NULL AND user_id = %s AND deleted_at IS NULL", (uid,))
            res_reb = cursor.fetchone()
            if res_reb and res_reb[0]: view_data['valor_rebanho'] = f"{res_reb[0]:,.2f}"

            cursor.execute("SELECT ano, total_entradas, total_compras, total_med, total_ops FROM v_fluxo_caixa WHERE user_id = %s ORDER BY ano DESC", (uid,))
            hist = cursor.fetchall()
            if hist:
                anos = [row[0] for row in hist]
                sal = sum(r[1] for r in hist) - sum(r[2]+r[3]+r[4] for r in hist)
                view_data['saldo_total_operacao'] = f"{sal:,.2f}"
                view_data['classe_saldo'] = 'bg-verde' if sal >= 0 else 'bg-vermelho'
                d_ano = next((r for r in hist if r[0] == ano_sel), None)
                if d_ano:
                    view_data['entradas_ano'], view_data['reposicao_ano'], view_data['med_ano'], view_data['custos_op_ano'] = [f"{x:,.2f}" for x in d_ano[1:]]
                    view_data['saidas_ano'] = f"{(d_ano[2]+d_ano[3]+d_ano[4]):,.2f}"
                    view_data['balanco_ano'] = f"{(d_ano[1] - (d_ano[2]+d_ano[3]+d_ano[4])):,.2f}"

            kpis = calcular_kpis_unificados(cursor, uid)
            if kpis['custo_arroba'] > 0:
                view_data['custo_diaria'] = f"{kpis['custo_diaria']:.2f}"
                view_data['custo_arroba'] = f"{kpis['custo_arroba']:.2f}"

            cursor.execute("SELECT data_custo, categoria, tipo_custo, valor, descricao FROM custos_operacionais WHERE user_id = %s AND YEAR(data_custo) = %s AND deleted_at IS NULL ORDER BY data_custo DESC", (uid, ano_sel))
            lista_custos = cursor.fetchall()
    except Exception as e:
        logger.error(f"Erro financeiro: {e}", exc_info=True)

    return render_template('financeiro.html', financeiro=view_data, ano_selecionado=ano_sel, anos=anos, detalhes_custos=lista_custos)

@financeiro_bp.route('/simulador-custo', methods=['GET', 'POST'])
@login_required
def simulador_custo():
    res, sugestoes = None, {'qtd_animais': 0, 'gmd_medio': 0.0, 'arrendamento': 0.0, 'suplementacao': 0.0, 'mao_obra': 0.0, 'extras': 0.0}
    try:
        if request.method == 'GET':
            with get_db_cursor() as cursor:
                sugestoes = calcular_kpis_unificados(cursor, current_user.id)
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
            
            sugestoes.update({'qtd_animais': qtd, 'gmd_medio': gmd, 'arrendamento': c_arr, 'suplementacao': c_sup, 'mao_obra': c_mao, 'extras': c_ext})
            
            c_men = c_arr + c_sup + c_mao + c_ext
            c_dia = (c_men / qtd / 30) if qtd > 0 else 0
            d_arr = (30 / gmd) if gmd > 0 else 0
            c_arr_val = c_dia * d_arr
            
            res = {'custo_mensal_total': f"{c_men:,.2f}", 'custo_diaria': f"{c_dia:,.2f}", 'dias_arroba': int(d_arr), 'custo_arroba': f"{c_arr_val:,.2f}"}
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
            
            with get_db_cursor() as cursor:
                cursor.execute("INSERT INTO custos_operacionais (user_id, categoria, tipo_custo, valor, data_custo, descricao) VALUES (%s, %s, %s, %s, %s, %s)", (current_user.id, cat, tipo, val, dt, desc))
                msg = "Custo registrado com sucesso."
        except Exception as e:
            logger.error(f"Erro custos: {e}", exc_info=True)
            msg = f"Erro: {e}"

    cats_fixo = []
    cats_variavel = []
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT nome, categoria FROM cost_centers ORDER BY nome")
            for nome, cat in cursor.fetchall():
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
            descricao = request.form.get('descricao')
            valor = float(request.form.get('valor'))
            vencimento = request.form.get('vencimento')
            
            with get_db_cursor() as cursor:
                sql = """
                    INSERT INTO financial_schedule (user_id, descricao, valor, vencimento, status)
                    VALUES (%s, %s, %s, %s, 'pendente')
                """
                cursor.execute(sql, (current_user.id, descricao, valor, vencimento))
                msg = "✅ Agendamento salvo com sucesso!"
        except Exception as e:
            logger.error(f"Erro ao agendar: {e}", exc_info=True)
            msg = f"❌ Erro ao salvar: {e}"

    contas = []
    try:
        with get_db_cursor() as cursor:
            sql_get = """
                SELECT id, descricao, valor, vencimento, status 
                FROM financial_schedule 
                WHERE user_id = %s AND deleted_at IS NULL 
                ORDER BY vencimento ASC
            """
            cursor.execute(sql_get, (current_user.id,))
            contas = cursor.fetchall()
    except Exception as e:
        logger.error(f"Erro lista agendamentos: {e}", exc_info=True)

    return render_template('agendamentos.html', agendamentos=contas, mensagem=msg, hoje=hoje) 



@financeiro_bp.route('/financeiro/baixar/<int:id_agendamento>')
@login_required
def baixar_agendamento(id_agendamento):
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT descricao, valor 
                FROM financial_schedule 
                WHERE id = %s AND user_id = %s AND status = 'pendente'
            """, (id_agendamento, current_user.id))
            
            item = cursor.fetchone()

            if item:
                descricao_origem = item[0]
                valor_pagamento = item[1]
                data_hoje = date.today()

                cursor.execute("""
                    UPDATE financial_schedule 
                    SET status = 'pago' 
                    WHERE id = %s
                """, (id_agendamento,))

                sql_ponte = """
                    INSERT INTO custos_operacionais 
                    (user_id, categoria, tipo_custo, valor, data_custo, descricao) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql_ponte, (
                    current_user.id, 
                    'Financeiro',        
                    'Agendamento',      
                    valor_pagamento, 
                    data_hoje,          
                    f"{descricao_origem} (Via Agendamento)"
                ))

    except Exception as e:
        logger.error(f"Erro ao dar baixa: {e}", exc_info=True)

    return redirect(url_for('financeiro.agendamentos'))   