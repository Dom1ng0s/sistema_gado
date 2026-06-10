from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
import math
import logging
from repositories import animal_repository, reproducao_repository
from routes.validators import validate

operacional_bp = Blueprint('operacional', __name__)
logger = logging.getLogger(__name__)

@operacional_bp.route('/painel')
@login_required
def painel():
    animais, termo, status = [], request.args.get('busca', ''), request.args.get('status', 'todos')
    pg = request.args.get('page', 1, type=int)
    limit, offset = 20, (pg - 1) * 20
    total_pg = 1

    try:
        total = animal_repository.count_animais(current_user.id, termo, status)
        animais = animal_repository.get_animais_paginados(current_user.id, limit, offset, termo, status)
        if total > 0:
            total_pg = math.ceil(total / limit)
    except Exception as e:
        logger.error(f"Erro painel: {e}", exc_info=True)

    return render_template("index.html", lista_animais=animais, pagina_atual=pg, total_paginas=total_pg, busca=termo, status=status)

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

@operacional_bp.route('/restaurar_animal/<int:id_animal>')
@login_required
def restaurar_animal(id_animal):
    try:
        animal_repository.restore_animal(id_animal, current_user.id)
    except Exception as e:
        logger.error(f"Erro restaurar: {e}", exc_info=True)
    return redirect(url_for('operacional.lixeira'))

@operacional_bp.route("/cadastro", methods=["GET", "POST"])
@login_required
def cadastro():
    msg = None
    if request.method == "POST":
        errors = validate(request.form, [
            ('brinco',       {'required': True, 'type': 'str',   'max_len': 50,   'label': 'Brinco'}),
            ('sexo',         {'required': True, 'choices': ['M', 'F'],             'label': 'Sexo'}),
            ('data_compra',  {'required': True, 'type': 'date',                   'label': 'Data de compra'}),
            ('peso_compra',  {'required': True, 'type': 'float', 'min_val': 0.1,  'max_val': 2000, 'label': 'Peso de compra'}),
            ('valor_arroba', {'required': True, 'type': 'float', 'min_val': 0.01,                  'label': 'Valor da arroba'}),
        ])
        if errors:
            return render_template("cadastro.html", mensagem=errors[0]), 400
        try:
            brinco = request.form["brinco"].strip()
            sexo = request.form["sexo"]
            data = request.form["data_compra"]
            peso = float(request.form["peso_compra"])
            val_arr = float(request.form["valor_arroba"])

            if animal_repository.check_brinco_exists(brinco, current_user.id):
                return render_template("cadastro.html", mensagem="Brinco já existe."), 400

            animal_repository.cadastrar_animal(brinco, sexo, data, (peso / 30) * val_arr, peso, current_user.id)
            return render_template("cadastro.html", mensagem_ok=f"Animal {brinco} cadastrado com sucesso.")
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
            'custo_total': f"{(float(animal[4] or 0) + sum(float(m[4] or 0) for m in meds)):.2f}",
        }

        return render_template("detalhes.html", animal=animal, historico_peso=pesagens, historico_med=meds, indicadores=kpis)
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

@operacional_bp.route('/excluir_animal/<int:id_animal>')
@login_required
def excluir_animal(id_animal):
    try:
        animal_repository.soft_delete_animal(id_animal, current_user.id)
    except Exception as e:
        logger.error(f"Erro excluir: {e}", exc_info=True)
    return redirect(url_for('operacional.painel'))

@operacional_bp.route('/excluir_pesagem/<int:id_pesagem>')
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
                request.form['obs']
            )
            return redirect(url_for('operacional.painel'))
        except Exception as e:
            logger.error(f"Erro vacinacao lote: {e}", exc_info=True)
            return "Erro ao processar vacinação."

    try:
        lista_animais = animal_repository.get_animais_ativos(current_user.id)
        return render_template('vacinacao_lote.html', animais=lista_animais)
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
            return render_template("cadastro_lote.html", mensagem=errors[0]), 400
        try:
            codigo_lote = request.form["codigo_lote"].strip()
            descricao = request.form["descricao"]
            data_compra = request.form["data_compra"]
            valor_arroba = float(request.form["valor_arroba"])
            sexos = request.form.getlist('sexos[]')

            animais_data = [
                (brinco, sexo, float(peso_txt), (float(peso_txt) / 30) * valor_arroba)
                for brinco, sexo, peso_txt in zip(brincos, sexos, pesos_str)
            ]

            animal_repository.cadastrar_lote(
                current_user.id, codigo_lote, descricao, data_compra, animais_data
            )
            msg = f"Lote '{codigo_lote}' salvo com {len(brincos)} animais e pesos individuais!"
        except Exception as e:
            logger.error(f"Erro cadastro lote: {e}", exc_info=True)
            msg = f"Erro ao processar lote: {e}"

    return render_template("cadastro_lote.html", mensagem=msg)


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
    eventos   = reproducao_repository.get_reproducao_by_vaca(id_animal, current_user.id)
    stats     = animal_repository.get_historico_reproducao(id_animal, current_user.id)
    machos    = animal_repository.get_animais_ativos_por_sexo(current_user.id, 'M')
    return render_template('animal_reproducao.html',
                           animal=animal, eventos=eventos,
                           stats=stats, machos=machos)


@operacional_bp.route('/reproducao', methods=['POST'])
@login_required
def registrar_reproducao():
    from routes.validators import validate
    id_animal = request.form.get('vaca_id', type=int)

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

    if not id_animal or not animal_repository.get_animal_by_id(id_animal, current_user.id):
        return redirect(url_for('operacional.painel'))

    if erros:
        from flask import flash
        for e in erros:
            flash(e, 'erro')
        return redirect(url_for('operacional.reproducao_animal', id_animal=id_animal))

    reproducao_repository.insert_reproducao(
        current_user.id,
        id_animal,
        int(touro_id_raw) if touro_id_raw else None,
        touro_externo,
        request.form.get('data_cobertura'),
        request.form.get('data_parto') or None,
        request.form.get('resultado'),
    )
    from flask import flash
    flash('Evento reprodutivo registrado com sucesso.', 'sucesso')
    return redirect(url_for('operacional.reproducao_animal', id_animal=id_animal))


@operacional_bp.route('/rebanho/ranking-touros')
@login_required
def ranking_touros():
    ranking   = animal_repository.get_ranking_touros(current_user.id)
    gmd_medio = animal_repository.get_gmd_medio_rebanho(current_user.id)
    return render_template('ranking_touros.html', ranking=ranking, gmd_medio=gmd_medio)
