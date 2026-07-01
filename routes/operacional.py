from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
import math
import logging
import csv
import io
import re as _re
from mysql.connector import errors as _mysql_errors
from datetime import date as _date
from repositories import animal_repository, reproducao_repository, sanitario_repository
from routes.validators import validate
from decimal import Decimal

operacional_bp = Blueprint('operacional', __name__)
logger = logging.getLogger(__name__)

@operacional_bp.route('/painel')
@login_required
def painel():
    animais, termo, status = [], request.args.get('busca', ''), request.args.get('status', 'todos')
    raca = request.args.get('raca', '') or None
    origem = request.args.get('origem', '') or None
    pg = request.args.get('page', 1, type=int)
    limit, offset = 20, (pg - 1) * 20
    total_pg = 1
    total = 0
    racas_disponiveis = []

    alertas_sanitarios = []
    try:
        racas_disponiveis = animal_repository.get_racas_distintas(current_user.id)
        total = animal_repository.count_animais(current_user.id, termo, status, raca=raca, origem=origem)
        animais = animal_repository.get_animais_paginados(current_user.id, limit, offset, termo, status,
                                                           raca=raca, origem=origem)
        if total > 0:
            total_pg = math.ceil(total / limit)
        alertas_sanitarios = sanitario_repository.get_vencendo_em_dias(current_user.id, dias=7)
    except Exception as e:
        logger.error(f"Erro painel: {e}", exc_info=True)

    return render_template("index.html", lista_animais=animais, pagina_atual=pg,
                           total_paginas=total_pg, total_animais=total, busca=termo, status=status,
                           raca_filtro=raca or '', racas_disponiveis=racas_disponiveis,
                           origem_filtro=origem or '',
                           alertas_sanitarios=alertas_sanitarios)

@operacional_bp.route('/lixeira')
@login_required
def lixeira():
    animais = []
    termo = request.args.get('busca', '')
    pg = request.args.get('page', 1, type=int)
    limit, offset = 20, (pg - 1) * 20
    total_pg = 1

    try:
        total = animal_repository.count_animais_lixeira(current_user.id, termo)
        animais = animal_repository.get_animais_lixeira_paginados(current_user.id, limit, offset, termo)
        if total > 0:
            total_pg = math.ceil(total / limit)
    except Exception as e:
        logger.error(f"Erro lixeira: {e}", exc_info=True)

    return render_template("lixeira.html", lista_animais=animais, pagina_atual=pg, total_paginas=total_pg, busca=termo)

@operacional_bp.route('/restaurar_animal/<int:id_animal>', methods=['POST'])
@login_required
def restaurar_animal(id_animal):
    try:
        animal_repository.restore_animal(id_animal, current_user.id)
    except Exception as e:
        logger.error(f"Erro restaurar: {e}", exc_info=True)
    return redirect(url_for('operacional.lixeira'))

@operacional_bp.route('/transacoes')
@login_required
def transacoes():
    return render_template('transacoes.html')

@operacional_bp.route("/cadastro", methods=["GET", "POST"])
@login_required
def cadastro():
    msg = None
    if request.method == "POST":
        errors = validate(request.form, [
            ('brinco',          {'required': True,  'type': 'str',   'max_len': 50,   'label': 'Brinco'}),
            ('sexo',            {'required': True,  'choices': ['M', 'F'],             'label': 'Sexo'}),
            ('raca',            {'required': False, 'type': 'str',   'max_len': 100,  'label': 'Raça'}),
            ('data_nascimento', {'required': False, 'type': 'date',                   'label': 'Data de nascimento'}),
            ('data_compra',     {'required': False, 'type': 'date',                   'label': 'Data de compra'}),
            ('peso_compra',     {'required': False, 'type': 'float', 'min_val': 0.1,  'max_val': 2000, 'label': 'Peso de entrada'}),
            ('valor_arroba',    {'required': False, 'type': 'float', 'min_val': 0.01,                  'label': 'Valor da arroba'}),
        ])

        data_compra = request.form.get('data_compra', '').strip() or None
        data_nascimento = request.form.get('data_nascimento', '').strip() or None

        if not data_compra and not data_nascimento:
            errors.append('Informe a data de compra (animal comprado) ou a data de nascimento (nascido na fazenda).')

        if errors:
            return render_template("cadastro.html", mensagem=errors[0]), 400

        try:
            brinco = request.form["brinco"].strip()
            sexo = request.form["sexo"]
            raca_raw = request.form.get("raca", "").strip()
            raca_outra = request.form.get("raca_outra", "").strip()
            raca = raca_outra if raca_raw == '__outra__' else (raca_raw or None)

            peso_str = request.form.get("peso_compra", "").strip()
            val_arr_str = request.form.get("valor_arroba", "").strip()

            peso = float(peso_str) if peso_str else None
            val_arr = float(val_arr_str) if val_arr_str else None
            preco_compra = (peso / 30) * val_arr if (peso and val_arr) else None

            if animal_repository.check_brinco_exists(brinco, current_user.id):
                return render_template("cadastro.html", mensagem="Brinco já existe."), 400

            new_id = animal_repository.cadastrar_animal(
                brinco, sexo, data_compra, preco_compra, peso, current_user.id,
                data_nascimento=data_nascimento, raca=raca,
            )
            flash(f"Animal {brinco} cadastrado com sucesso.", 'success')
            return redirect(url_for('operacional.detalhes', id_animal=new_id))
        except Exception as e:
            logger.error(f"Erro cadastro: {e}", exc_info=True)
            msg = f"Erro: {e}"
    return render_template("cadastro.html", mensagem=msg)

@operacional_bp.route('/animal/<int:id_animal>')
@login_required
def detalhes(id_animal):
    try:
        animal = animal_repository.get_animal_by_id(id_animal, current_user.id)
        if not animal:
            return redirect(url_for('operacional.painel'))

        pesagens = animal_repository.get_pesagens_by_animal(id_animal)
        meds = animal_repository.get_medicacoes_by_animal(id_animal)
        view = animal_repository.get_gmd_by_animal(id_animal)

        kpis = {
            'peso_atual': view[0] if view else (pesagens[0][3] if pesagens else 0),
            'ganho_total': view[1] if view else 0,
            'dias': view[2] if view else 0,
            'gmd': "{:.3f}".format(view[3]) if view else "0.000",
            'custo_total': f"{(float(animal[5] or 0) + sum(float(m[4] or 0) for m in meds)):.2f}",
        }

        # Índices da query explícita em get_animal_by_id:
        # 0=id 1=brinco 2=sexo 3=raca 4=data_compra 5=preco_compra 6=data_venda
        # 7=preco_venda 8=user_id 9=lote_id 10=deleted_at 11=pai_id 12=mae_id 13=data_nascimento
        data_nasc = animal[13]
        idade_meses = None
        if data_nasc:
            delta = (_date.today() - data_nasc).days
            idade_meses = delta // 30

        return render_template("detalhes.html", animal=animal, historico_peso=pesagens,
                               historico_med=meds, indicadores=kpis, idade_meses=idade_meses)
    except Exception as e:
        logger.error(f"Erro detalhes: {e}", exc_info=True)
        return redirect(url_for('operacional.painel'))

@operacional_bp.route('/vender/<int:id_animal>', methods=['GET', 'POST'])
@login_required
def vender(id_animal):
    if request.method == 'POST':
        errors = validate(request.form, [
            ('data_venda',   {'required': True, 'type': 'date',                   'label': 'Data de venda'}),
            ('peso_venda',   {'required': True, 'type': 'float', 'min_val': 0.1,  'max_val': 2000, 'label': 'Peso de venda'}),
            ('valor_arroba', {'required': True, 'type': 'float', 'min_val': 0.01,                  'label': 'Valor da arroba'}),
        ])
        if errors:
            return render_template('vender.html', id_animal=id_animal, mensagem=errors[0]), 400
        try:
            dt = request.form['data_venda']
            peso = float(request.form['peso_venda'])
            val = float(request.form['valor_arroba'])
            animal_repository.registrar_venda(id_animal, current_user.id, dt, (peso / 30) * val, peso)
            return redirect(url_for('operacional.detalhes', id_animal=id_animal))
        except Exception as e:
            logger.error(f"Erro vender: {e}", exc_info=True)
    return render_template('vender.html', id_animal=id_animal)

@operacional_bp.route('/venda-lote', methods=['GET', 'POST'])
@login_required
def venda_lote():
    if request.method == 'POST':
        errors = validate(request.form, [
            ('data_venda',   {'required': True, 'type': 'date',  'label': 'Data de venda'}),
            ('valor_arroba', {'required': True, 'type': 'float', 'min_val': 0.01, 'label': 'Valor da arroba'}),
        ])
        if errors:
            animais = animal_repository.get_animais_ativos_com_ultimo_peso(current_user.id)
            return render_template('venda_lote.html', animais=animais, erro=errors[0]), 400

        animal_ids = request.form.getlist('animal_ids[]')
        pesos = request.form.getlist('pesos_venda[]')

        if not animal_ids:
            animais = animal_repository.get_animais_ativos_com_ultimo_peso(current_user.id)
            return render_template('venda_lote.html', animais=animais,
                                   erro="Selecione pelo menos um animal."), 400

        data_venda = request.form['data_venda']
        valor_arroba = float(request.form['valor_arroba'])

        vendas = []
        for aid_str, peso_str in zip(animal_ids, pesos):
            try:
                aid = int(aid_str)
                peso = float(peso_str)
                if peso <= 0:
                    raise ValueError
                vendas.append((aid, peso, round((peso / 30) * valor_arroba, 2)))
            except (ValueError, TypeError):
                animais = animal_repository.get_animais_ativos_com_ultimo_peso(current_user.id)
                return render_template('venda_lote.html', animais=animais,
                                       erro="Peso inválido em um ou mais animais."), 400

        try:
            vendidos, invalidos = animal_repository.registrar_venda_lote(vendas, current_user.id, data_venda)
        except Exception as e:
            logger.error(f"Erro venda lote: {e}", exc_info=True)
            animais = animal_repository.get_animais_ativos_com_ultimo_peso(current_user.id)
            return render_template('venda_lote.html', animais=animais,
                                   erro="Erro ao registrar venda. Tente novamente."), 400

        msg = f"{vendidos} animal(is) vendido(s) com sucesso."
        if invalidos:
            msg += f" {len(invalidos)} ignorado(s) (já vendido ou não pertence ao usuário)."
        flash(msg, 'success')
        return redirect(url_for('operacional.painel'))

    animais = animal_repository.get_animais_ativos_com_ultimo_peso(current_user.id)
    return render_template('venda_lote.html', animais=animais)

@operacional_bp.route('/medicar/<int:id_animal>', methods=['GET', 'POST'])
@login_required
def medicar(id_animal):
    if request.method == 'POST':
        errors = validate(request.form, [
            ('data_aplicacao', {'required': True,  'type': 'date',                  'label': 'Data de aplicação'}),
            ('nome',           {'required': True,  'type': 'str',  'max_len': 200,  'label': 'Nome do medicamento'}),
            ('custo',          {'required': True,  'type': 'float','min_val': 0,    'label': 'Custo'}),
            ('obs',            {'required': False, 'type': 'str',  'max_len': 500,  'label': 'Observação'}),
        ])
        if errors:
            return render_template('medicar.html', id_animal=id_animal, mensagem=errors[0]), 400
        try:
            animal_repository.registrar_medicacao(
                id_animal, current_user.id,
                request.form['data_aplicacao'], request.form['nome'],
                request.form['custo'], request.form['obs']
            )
            return redirect(url_for('operacional.detalhes', id_animal=id_animal))
        except Exception as e:
            logger.error(f"Erro medicar: {e}", exc_info=True)
    return render_template('medicar.html', id_animal=id_animal)

@operacional_bp.route('/pesar/<int:id_animal>', methods=['GET', 'POST'])
@login_required
def nova_pesagem(id_animal):
    if request.method == 'POST':
        errors = validate(request.form, [
            ('data_pesagem', {'required': True, 'type': 'date',                  'label': 'Data da pesagem'}),
            ('peso',         {'required': True, 'type': 'float','min_val': 0.1, 'max_val': 2000, 'label': 'Peso'}),
        ])
        if errors:
            return render_template('nova_pesagem.html', id_animal=id_animal, mensagem=errors[0]), 400
        try:
            animal_repository.registrar_pesagem(
                id_animal, current_user.id,
                request.form['data_pesagem'], request.form['peso']
            )
            return redirect(url_for('operacional.detalhes', id_animal=id_animal))
        except Exception as e:
            logger.error(f"Erro pesar: {e}", exc_info=True)
    return render_template('nova_pesagem.html', id_animal=id_animal)

@operacional_bp.route('/excluir_animal/<int:id_animal>', methods=['POST'])
@login_required
def excluir_animal(id_animal):
    try:
        animal_repository.soft_delete_animal(id_animal, current_user.id)
    except Exception as e:
        logger.error(f"Erro excluir: {e}", exc_info=True)
    return redirect(url_for('operacional.painel'))

@operacional_bp.route('/excluir_pesagem/<int:id_pesagem>', methods=['POST'])
@login_required
def excluir_pesagem(id_pesagem):
    aid = None
    try:
        aid = animal_repository.soft_delete_pesagem(id_pesagem, current_user.id)
    except Exception as e:
        logger.error(f"Erro excluir pesagem: {e}", exc_info=True)

    if aid:
        return redirect(url_for('operacional.detalhes', id_animal=aid))
    return redirect(url_for('operacional.painel'))

@operacional_bp.route('/vacinacao-coletiva', methods=['GET', 'POST'])
@login_required
def vacinacao_coletiva():
    if request.method == 'POST':
        try:
            animais_ids = request.form.getlist('animais_ids')
            if not animais_ids:
                return render_template('vacinacao_lote.html', erro="Nenhum animal selecionado!", animais=[]), 400

            errors = validate(request.form, [
                ('data_aplicacao', {'required': True,  'type': 'date',                  'label': 'Data de aplicação'}),
                ('nome',           {'required': True,  'type': 'str',  'max_len': 200,  'label': 'Nome do produto'}),
                ('custo',          {'required': True,  'type': 'float','min_val': 0,    'label': 'Custo'}),
                ('obs',            {'required': False, 'type': 'str',  'max_len': 500,  'label': 'Observação'}),
            ])
            if errors:
                lista_animais = animal_repository.get_animais_ativos(current_user.id)
                return render_template('vacinacao_lote.html', erro=errors[0], animais=lista_animais), 400

            animal_repository.insert_medicacao_lote(
                animais_ids,
                request.form['data_aplicacao'],
                request.form['nome'],
                request.form['custo'],
                request.form['obs'],
                user_id=current_user.id,
            )
            flash(f"{len(animais_ids)} animal(is) vacinado(s) com sucesso.", 'success')
            return redirect(url_for('operacional.painel'))
        except Exception as e:
            logger.error(f"Erro vacinacao lote: {e}", exc_info=True)
            lista_animais = animal_repository.get_animais_ativos(current_user.id)
            return render_template('vacinacao_lote.html', erro="Erro interno ao processar vacinação.", animais=lista_animais), 500

    try:
        lista_animais = animal_repository.get_animais_ativos(current_user.id)
        nome_pre = request.args.get('protocolo', '')
        return render_template('vacinacao_lote.html', animais=lista_animais, nome_pre=nome_pre)
    except Exception as e:
        logger.error(f"Erro carregar lote: {e}", exc_info=True)
        return redirect(url_for('operacional.painel'))

@operacional_bp.route("/cadastro-lote", methods=["GET", "POST"])
@login_required
def cadastro_lote():
    msg = None
    if request.method == "POST":
        errors = validate(request.form, [
            ('codigo_lote',  {'required': True,  'type': 'str',   'max_len': 100,  'label': 'Código do lote'}),
            ('data_compra',  {'required': True,  'type': 'date',                   'label': 'Data de compra'}),
            ('valor_arroba', {'required': True,  'type': 'float', 'min_val': 0.01, 'label': 'Valor da arroba'}),
            ('descricao',    {'required': False, 'type': 'str',   'max_len': 500,  'label': 'Descrição'}),
        ])
        brincos = request.form.getlist('brincos[]')
        pesos_str = request.form.getlist('pesos[]')
        if not brincos:
            errors.append("A tabela de animais está vazia.")
        else:
            if any(not b.strip() for b in brincos):
                errors.append("Todos os brincos devem ser preenchidos.")
            for i, p in enumerate(pesos_str, 1):
                try:
                    if float(p.replace(',', '.')) <= 0:
                        errors.append(f"Peso do animal {i} deve ser maior que zero.")
                except (ValueError, AttributeError):
                    errors.append(f"Peso do animal {i} é inválido.")
        if errors:
            restore_data = {
                'brincos': request.form.getlist('brincos[]'),
                'sexos': request.form.getlist('sexos[]'),
                'pesos': request.form.getlist('pesos[]'),
            }
            return render_template("cadastro_lote.html", mensagem=errors[0],
                                   form_data=request.form, restore_data=restore_data), 400
        try:
            codigo_lote = request.form["codigo_lote"].strip()
            descricao = request.form["descricao"]
            data_compra = request.form["data_compra"]
            valor_arroba = float(request.form["valor_arroba"])
            sexos = request.form.getlist('sexos[]')
            raca_raw = request.form.get("raca", "").strip()
            raca_outra = request.form.get("raca_outra", "").strip()
            raca = raca_outra if raca_raw == '__outra__' else (raca_raw or None)

            animais_data = [
                (brinco, sexo, float(peso_txt), (float(peso_txt) / 30) * valor_arroba)
                for brinco, sexo, peso_txt in zip(brincos, sexos, pesos_str)
            ]

            animal_repository.cadastrar_lote(
                current_user.id, codigo_lote, descricao, data_compra, animais_data, raca=raca
            )
            msg = f"Lote '{codigo_lote}' salvo com {len(brincos)} animais e pesos individuais!"
        except Exception as e:
            logger.error(f"Erro cadastro lote: {e}", exc_info=True)
            msg = f"Erro ao processar lote: {e}"

    return render_template("cadastro_lote.html", mensagem=msg)


@operacional_bp.route('/pesagem-lote', methods=['GET', 'POST'])
@login_required
def pesagem_lote():
    lote_id = request.args.get('lote_id', type=int)
    lotes = []
    animais = []
    msg = None

    try:
        lotes = animal_repository.get_lotes(current_user.id)

        if request.method == 'POST':
            animal_ids = request.form.getlist('animal_ids[]')
            pesos = request.form.getlist('pesos[]')

            if not animal_ids:
                animais = animal_repository.get_animais_ativos_por_lote(current_user.id, lote_id)
                return render_template('pesagem_lote.html', lotes=lotes, animais=animais,
                                       lote_id_selecionado=lote_id,
                                       erro="Selecione pelo menos um animal."), 400

            errors = validate(request.form, [
                ('data_pesagem', {'required': True, 'type': 'date', 'label': 'Data da pesagem'}),
            ])
            if errors:
                animais = animal_repository.get_animais_ativos_por_lote(current_user.id, lote_id)
                return render_template('pesagem_lote.html', lotes=lotes, animais=animais,
                                       lote_id_selecionado=lote_id, erro=errors[0]), 400

            pairs = []
            for aid_str, peso_str in zip(animal_ids, pesos):
                try:
                    aid = int(aid_str)
                    peso = float(peso_str)
                    if peso <= 0:
                        raise ValueError
                    pairs.append((aid, peso))
                except (ValueError, TypeError):
                    animais = animal_repository.get_animais_ativos_por_lote(current_user.id, lote_id)
                    return render_template('pesagem_lote.html', lotes=lotes, animais=animais,
                                           lote_id_selecionado=lote_id,
                                           erro="Peso inválido em um ou mais animais."), 400

            inseridos, invalidos = animal_repository.registrar_pesagens_lote(
                pairs, current_user.id, request.form['data_pesagem']
            )
            msg = f"{inseridos} pesagem(ns) registrada(s) com sucesso."
            if invalidos:
                msg += f" {len(invalidos)} animal(is) ignorado(s) (não pertence ao usuário)."
            flash(msg, 'success')
            return redirect(url_for('operacional.pesagem_lote', lote_id=lote_id))

        animais = animal_repository.get_animais_ativos_por_lote(current_user.id, lote_id)
    except Exception as e:
        logger.error(f"Erro pesagem lote: {e}", exc_info=True)

    return render_template('pesagem_lote.html', lotes=lotes, animais=animais,
                           lote_id_selecionado=lote_id)


# ════════════════════════════════════════════════════════════════════════════
# HEREDITARIEDADE
# ════════════════════════════════════════════════════════════════════════════

@operacional_bp.route('/animais/<int:id_animal>/progenie')
@login_required
def progenie_animal(id_animal):
    animal = animal_repository.get_animal_by_id(id_animal, current_user.id)
    if not animal:
        return redirect(url_for('operacional.painel'))
    filhos = animal_repository.get_progenie_by_touro(id_animal, current_user.id)
    return render_template('animal_progenie.html', animal=animal, filhos=filhos)


@operacional_bp.route('/animais/<int:id_animal>/reproducao')
@login_required
def reproducao_animal(id_animal):
    animal = animal_repository.get_animal_by_id(id_animal, current_user.id)
    if not animal:
        return redirect(url_for('operacional.painel'))
    eventos          = reproducao_repository.get_reproducao_by_vaca(id_animal, current_user.id)
    stats            = animal_repository.get_historico_reproducao(id_animal, current_user.id)
    machos           = animal_repository.get_animais_ativos_por_sexo(current_user.id, 'M')
    partos_previstos = []
    try:
        partos_previstos = reproducao_repository.get_partos_previstos(current_user.id, dias=60)
    except Exception:
        pass
    return render_template('animal_reproducao.html',
                           animal=animal, eventos=eventos,
                           stats=stats, machos=machos,
                           partos_previstos=partos_previstos)


@operacional_bp.route('/reproducao', methods=['POST'])
@login_required
def registrar_reproducao():
    from routes.validators import validate
    id_animal = request.form.get('vaca_id', type=int)

    resultado      = request.form.get('resultado', '')
    data_parto     = request.form.get('data_parto', '').strip() or None
    brinco_bezerro = request.form.get('brinco_bezerro', '').strip() or None
    sexo_bezerro   = request.form.get('sexo_bezerro', '').strip() or None

    erros = validate(request.form, [
        ('data_cobertura', {'label': 'Data de cobertura', 'required': True,  'type': 'date'}),
        ('data_parto',     {'label': 'Data de parto',     'required': False, 'type': 'date'}),
        ('resultado',      {'label': 'Resultado',          'required': True,
                            'choices': ['vivo', 'natimorto', 'aborto']}),
    ])
    touro_id_raw  = request.form.get('touro_id', '').strip()
    touro_externo = request.form.get('touro_externo', '').strip() or None

    if not touro_id_raw and not touro_externo:
        erros.append("Informe o touro (interno ou nome externo).")
    elif touro_id_raw:
        try:
            _tid = int(touro_id_raw)
            if not animal_repository.get_animal_by_id(_tid, current_user.id):
                erros.append("Touro informado não pertence ao seu rebanho.")
                touro_id_raw = ''
        except (ValueError, TypeError):
            erros.append("Touro informado é inválido.")
            touro_id_raw = ''

    if resultado == 'vivo' and data_parto:
        if not brinco_bezerro:
            erros.append("Informe o brinco do bezerro nascido.")
        if not sexo_bezerro or sexo_bezerro not in ('M', 'F'):
            erros.append("Informe o sexo do bezerro nascido.")

    if not id_animal or not animal_repository.get_animal_by_id(id_animal, current_user.id):
        return redirect(url_for('operacional.painel'))

    if erros:
        for e in erros:
            flash(e, 'error')
        return redirect(url_for('operacional.reproducao_animal', id_animal=id_animal))

    reproducao_repository.insert_reproducao(
        current_user.id,
        id_animal,
        int(touro_id_raw) if touro_id_raw else None,
        touro_externo,
        request.form.get('data_cobertura'),
        data_parto,
        resultado,
    )

    bezerro_msg = ''
    if resultado == 'vivo' and data_parto and brinco_bezerro and sexo_bezerro:
        if not animal_repository.check_brinco_exists(brinco_bezerro, current_user.id):
            bezerro_id = animal_repository.cadastrar_animal(
                brinco_bezerro, sexo_bezerro,
                data_compra=None, preco_compra=None, peso_entrada=None,
                user_id=current_user.id,
                data_nascimento=data_parto,
                mae_id=id_animal,
            )
            bezerro_msg = f' Bezerro criado automaticamente: brinco {brinco_bezerro} (ID #{bezerro_id}).'
        else:
            bezerro_msg = f' Brinco {brinco_bezerro} já existia — bezerro não duplicado.'

    flash(f'Evento reprodutivo registrado com sucesso.{bezerro_msg}', 'success')
    return redirect(url_for('operacional.reproducao_animal', id_animal=id_animal))


@operacional_bp.route('/reproducao/<int:rep_id>/diagnostico', methods=['POST'])
@login_required
def registrar_diagnostico(rep_id):
    erros = validate(request.form, [
        ('diagnostico',      {'required': True,  'choices': ['positivo', 'negativo'], 'label': 'Diagnóstico'}),
        ('data_diagnostico', {'required': True,  'type': 'date',                      'label': 'Data do DG'}),
    ])
    id_animal = request.form.get('vaca_id', type=int)

    if erros:
        for e in erros:
            flash(e, 'error')
    else:
        try:
            reproducao_repository.update_diagnostico(
                rep_id,
                current_user.id,
                request.form.get('diagnostico'),
                request.form.get('data_diagnostico'),
            )
            flash('Diagnóstico registrado com sucesso.', 'success')
        except Exception as e:
            logger.error(f"Erro DG {rep_id}: {e}", exc_info=True)
            flash('Erro ao registrar diagnóstico.', 'error')

    if id_animal:
        return redirect(url_for('operacional.reproducao_animal', id_animal=id_animal))
    return redirect(url_for('operacional.painel'))


@operacional_bp.route('/rebanho/ranking-touros')
@login_required
def ranking_touros():
    import logging as _log
    try:
        ranking = animal_repository.get_ranking_touros(current_user.id)
        gmd_medio_raw = animal_repository.get_gmd_medio_rebanho(current_user.id)
        
        # Converte o valor retornado para Decimal, ou usa Decimal('0.0') se vier vazio/None
        gmd_medio = Decimal(str(gmd_medio_raw)) if gmd_medio_raw else Decimal('0.0')
        
    except Exception:
        _log.exception("Erro em ranking_touros user_id=%s", current_user.id)
        # Substitui o 0.0 (float) por Decimal('0.0') no fallback do erro
        ranking, gmd_medio = [], Decimal('0.0')
        
    return render_template('ranking_touros.html', ranking=ranking, gmd_medio=gmd_medio)

_CSV_COLUNAS_OBRIGATORIAS = {'brinco', 'sexo', 'data_compra', 'peso_kg', 'valor_arroba'}
_CSV_MAX_BYTES = 1 * 1024 * 1024  # 1 MB
_CSV_MAX_LINHAS = 5000


@operacional_bp.route('/importar-csv', methods=['GET', 'POST'])
@login_required
def importar_csv():
    if request.method == 'GET':
        return render_template('importar_csv.html')

    arquivo = request.files.get('arquivo')
    if not arquivo or not arquivo.filename:
        return render_template('importar_csv.html', erro="Selecione um arquivo CSV.")

    conteudo = arquivo.read()
    if len(conteudo) > _CSV_MAX_BYTES:
        return render_template('importar_csv.html', erro="Arquivo excede 1 MB.")

    try:
        texto = conteudo.decode('utf-8-sig')
    except UnicodeDecodeError:
        return render_template('importar_csv.html', erro="Arquivo deve estar em UTF-8.")

    reader = csv.DictReader(io.StringIO(texto))
    faltando = _CSV_COLUNAS_OBRIGATORIAS - set(reader.fieldnames or [])
    if faltando:
        return render_template('importar_csv.html',
                               erro=f"Colunas obrigatórias ausentes: {', '.join(sorted(faltando))}")

    inseridos, erros = 0, []

    try:
        from db_config import get_db_cursor
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT brinco FROM animais WHERE user_id = %s AND deleted_at IS NULL",
                (current_user.id,)
            )
            brincos_existentes = {row[0] for row in cursor.fetchall()}

            for i, row in enumerate(reader, start=2):
                if i - 1 > _CSV_MAX_LINHAS:
                    erros.append({'linha': i, 'msg': 'Limite de 5000 linhas atingido — importação interrompida.'})
                    break

                brinco      = (row.get('brinco') or '').strip()
                sexo        = (row.get('sexo') or '').strip().upper()
                data_compra = (row.get('data_compra') or '').strip()
                raca        = (row.get('raca') or '').strip() or None
                data_nasc   = (row.get('data_nascimento') or '').strip() or None

                linha_erros = []
                if not brinco:
                    linha_erros.append("brinco vazio")
                if sexo not in ('M', 'F'):
                    linha_erros.append("sexo inválido (use M ou F)")

                preco_compra = None
                try:
                    peso = float((row.get('peso_kg') or '').replace(',', '.'))
                    arr  = float((row.get('valor_arroba') or '').replace(',', '.'))
                    if peso <= 0 or arr <= 0:
                        raise ValueError
                    preco_compra = round((peso / 30) * arr, 2)
                except (ValueError, TypeError):
                    linha_erros.append("peso_kg ou valor_arroba inválido")

                if data_compra and not _re.match(r'^\d{4}-\d{2}-\d{2}$', data_compra):
                    linha_erros.append("data_compra deve ser AAAA-MM-DD")
                if data_nasc and not _re.match(r'^\d{4}-\d{2}-\d{2}$', data_nasc):
                    linha_erros.append("data_nascimento deve ser AAAA-MM-DD")

                if not data_compra and not data_nasc:
                    linha_erros.append("informe data_compra ou data_nascimento")

                if linha_erros:
                    erros.append({'linha': i, 'msg': '; '.join(linha_erros)})
                    continue

                if brinco in brincos_existentes:
                    erros.append({'linha': i, 'msg': f"brinco '{brinco}' já existe"})
                    continue

                try:
                    cursor.execute(
                        "INSERT INTO animais (brinco, sexo, raca, data_compra, data_nascimento, "
                        "preco_compra, user_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                        (brinco, sexo, raca, data_compra or None,
                         data_nasc or None, preco_compra, current_user.id)
                    )
                    brincos_existentes.add(brinco)
                    inseridos += 1
                except _mysql_errors.IntegrityError:
                    erros.append({'linha': i, 'msg': f"brinco '{brinco}' já existe (conflito)"})

    except Exception as e:
        logger.error(f"Erro importação CSV: {e}", exc_info=True)
        return render_template('importar_csv.html',
                               erro="Erro interno ao processar importação. Verifique os dados e tente novamente.")

    return render_template('importar_csv.html',
                           resultado={'inseridos': inseridos, 'erros': erros})
