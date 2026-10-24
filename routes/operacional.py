from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
import math
import logging
import csv
import io
import re as _re
from db_config import IntegrityError as _IntegrityError
from datetime import date as _date
from repositories import (animal_repository, financeiro_repository, reproducao_repository,
                          sanitario_repository)
from routes.validators import validate
from utils.calculo import preco_por_arroba
from utils.carencia import dias_carencia_sugerido
from decimal import Decimal

operacional_bp = Blueprint('operacional', __name__)
logger = logging.getLogger(__name__)


def _msg_carencia(carencias):
    """Mensagem de bloqueio: brinco, produto e a data em que libera.

    Quem está no curral precisa dos três — sem o brinco não sabe qual animal
    tirar da lista, e sem a data não sabe quando voltar.
    """
    por_animal = {}
    for animal_id, brinco, _med_id, nome, _aplic, _dias, liberacao, _restantes in carencias:
        atual = por_animal.get(animal_id)
        if atual is None or liberacao > atual[1]:
            por_animal[animal_id] = (brinco, liberacao, nome)
    partes = [f"{brinco} ({nome}, libera em {liberacao.strftime('%d/%m/%Y')})"
              for brinco, liberacao, nome in sorted(por_animal.values())]
    plural = "animais" if len(partes) > 1 else "animal"
    return (f"Carência sanitária: {len(partes)} {plural} não pode(m) ir para o abate — "
            + "; ".join(partes) + ".")


def _dias_carencia_do_form(form):
    """Carência declarada no formulário; em branco, cai na sugestão pelo nome.

    Campo vazio não é "sem carência": é usuário que não preencheu, e para
    Ivermectina o silêncio custa a carcaça. Zero explícito é respeitado.
    """
    bruto = (form.get('dias_carencia') or '').strip()
    if bruto:
        try:
            return max(0, int(bruto))
        except (TypeError, ValueError):
            pass
    return dias_carencia_sugerido(form.get('nome'))

@operacional_bp.route('/inicio')
@login_required
def inicio():
    """O que precisa de atenção hoje, reunido num lugar só.

    Os quatro sinais já existiam, cada um escondido numa tela diferente:
    GMD fora da faixa no painel, parto vencido em Reprodução, protocolo
    a vencer em Sanidade e conta a vencer em Financeiro. Nenhuma tela
    respondia "o que precisa de mim agora", que é a pergunta de quem
    abre o sistema sem uma tarefa específica em mente.

    Cada fonte é isolada: uma consulta que falhe não leva a tela junto,
    só perde a sua linha.
    """
    hoje = _date.today()
    leituras = {'gmd_medio': None, 'total_animais': 0, 'abaixo_gmd': 0, 'a_pagar_30d': Decimal('0')}
    ocorrencias = []

    try:
        leituras['gmd_medio'] = animal_repository.get_gmd_medio_rebanho(current_user.farm_id)
        leituras['total_animais'] = animal_repository.count_animais(current_user.farm_id, status='ativos')
        abaixo = animal_repository.get_animais_abaixo_gmd_medio(current_user.farm_id)
        leituras['abaixo_gmd'] = len(abaixo)
        if abaixo:
            ocorrencias.append({
                'tom': 'limite',
                'titulo': 'Animais com ganho muito abaixo do lote',
                'detalhe': 'Crescem significativamente menos que os demais; verifique saúde, nutrição e parasitas',
                'numero': len(abaixo),
                'acao': 'Ver no rebanho',
                'href': url_for('operacional.painel'),
            })
    except Exception as e:
        logger.error(f"Erro Início (rebanho): {e}", exc_info=True)

    try:
        partos = reproducao_repository.get_partos_previstos(current_user.farm_id, dias=285)
        atrasados = [p for p in partos if p[4] <= 0]
        if atrasados:
            ocorrencias.append({
                'tom': 'limite',
                'titulo': 'Partos previstos já vencidos',
                'detalhe': 'Confirme o parto na ficha reprodutiva — o bezerro entra no rebanho automaticamente',
                'numero': len(atrasados),
                'acao': 'Abrir agenda',
                'href': url_for('operacional.reproducao_painel'),
            })
    except Exception as e:
        logger.error(f"Erro Início (reprodução): {e}", exc_info=True)

    try:
        protocolos = sanitario_repository.get_vencendo_em_dias(current_user.farm_id, dias=7)
        for p in protocolos:
            dias = (p[2] - hoje).days if p[2] else None
            ocorrencias.append({
                'tom': 'limite' if (dias is not None and dias <= 3) else 'dado',
                'titulo': p[1],
                'detalhe': 'Protocolo sanitário a vencer',
                'numero': f'{dias} d' if dias is not None else '—',
                'acao': 'Ver protocolo',
                'href': url_for('sanitario.lista_protocolos'),
            })
    except Exception as e:
        logger.error(f"Erro Início (sanidade): {e}", exc_info=True)

    try:
        carencias = sanitario_repository.get_carencias_ativas(current_user.farm_id)
        if carencias:
            brincos = sorted({c[1] for c in carencias})
            liberacao = max(c[6] for c in carencias)
            ocorrencias.append({
                'tom': 'limite',
                'titulo': 'Animais em carência sanitária',
                'detalhe': ('Não podem ir para o abate; último libera em '
                            f'{liberacao.strftime("%d/%m/%Y")} ('
                            + ', '.join(brincos[:4])
                            + (f' e mais {len(brincos) - 4}' if len(brincos) > 4 else '') + ')'),
                'numero': len(brincos),
                'acao': 'Ver no rebanho',
                'href': url_for('operacional.painel'),
            })
    except Exception as e:
        logger.error(f"Erro Início (carência): {e}", exc_info=True)

    try:
        paradas = animal_repository.get_lotes_sem_pesagem(current_user.farm_id, dias=45)
        if paradas:
            ocorrencias.append({
                'tom': 'dado',
                'titulo': 'Lotes sem pesagem há 45 dias ou mais',
                'detalhe': ('Sem pesagem não há GMD, e sem GMD não há como saber se o lote '
                            f'está engordando — o mais antigo está há {paradas[0][4]} dias'),
                'numero': len(paradas),
                'acao': 'Pesar em lote',
                'href': url_for('operacional.pesagem_lote'),
            })
    except Exception as e:
        logger.error(f"Erro Início (pesagem de lote): {e}", exc_info=True)

    try:
        for ag in financeiro_repository.get_agendamentos(current_user.farm_id):
            if (ag[4] or '').lower() == 'pago' or not ag[3]:
                continue
            dias = (ag[3] - hoje).days
            if dias > 30:
                continue
            leituras['a_pagar_30d'] += (ag[2] or Decimal('0'))
            if dias <= 0:
                ocorrencias.append({
                    'tom': 'limite',
                    'titulo': ag[1],
                    'detalhe': 'Conta vencida' if dias < 0 else 'Conta vence hoje',
                    'numero': ag[2],
                    'moeda': True,
                    'acao': 'Dar baixa',
                    'href': url_for('financeiro.agendamentos'),
                })
    except Exception as e:
        logger.error(f"Erro Início (financeiro): {e}", exc_info=True)

    return render_template('inicio.html', leituras=leituras, ocorrencias=ocorrencias, hoje=hoje)


@operacional_bp.route('/painel')
@login_required
def painel():
    animais, termo, status = [], request.args.get('busca', ''), request.args.get('status', 'todos')
    raca = request.args.get('raca', '') or None
    origem = request.args.get('origem', '') or None
    sexo = request.args.get('sexo', '') or None
    if sexo not in ('M', 'F'):
        sexo = None
    ordem = animal_repository.normalizar_ordenacao(request.args.get('ord', ''))
    pg = request.args.get('page', 1, type=int)
    limit, offset = 20, (pg - 1) * 20
    total_pg = 1
    total = 0
    racas_disponiveis = []

    alertas_sanitarios = []
    try:
        racas_disponiveis = animal_repository.get_racas_distintas(current_user.farm_id)
        total = animal_repository.count_animais(current_user.farm_id, termo, status, raca=raca, origem=origem, sexo=sexo)
        animais = animal_repository.get_animais_paginados(current_user.farm_id, limit, offset, termo, status,
                                                           raca=raca, origem=origem, sexo=sexo, ordem=ordem)
        if total > 0:
            total_pg = math.ceil(total / limit)
        alertas_sanitarios = sanitario_repository.get_vencendo_em_dias(current_user.farm_id, dias=7)
    except Exception as e:
        logger.error(f"Erro painel: {e}", exc_info=True)
        flash("Não foi possível carregar o rebanho agora. Tente novamente em instantes.", 'error')

    return render_template("index.html", lista_animais=animais, pagina_atual=pg,
                           total_paginas=total_pg, total_animais=total, busca=termo, status=status,
                           raca_filtro=raca or '', racas_disponiveis=racas_disponiveis,
                           origem_filtro=origem or '', sexo_filtro=sexo or '',
                           ordenacao=ordem,
                           gmd_embutido=animal_repository.ordenacao_traz_gmd(ordem),
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
        total = animal_repository.count_animais_lixeira(current_user.farm_id, termo)
        animais = animal_repository.get_animais_lixeira_paginados(current_user.farm_id, limit, offset, termo)
        if total > 0:
            total_pg = math.ceil(total / limit)
    except Exception as e:
        logger.error(f"Erro lixeira: {e}", exc_info=True)
        flash("Não foi possível carregar a lixeira agora. Tente novamente em instantes.", 'error')

    return render_template("lixeira.html", lista_animais=animais, pagina_atual=pg, total_paginas=total_pg, busca=termo)

@operacional_bp.route('/restaurar_animal/<int:id_animal>', methods=['POST'])
@login_required
def restaurar_animal(id_animal):
    try:
        animal_repository.restore_animal(id_animal, current_user.farm_id)
    except Exception as e:
        logger.error(f"Erro restaurar: {e}", exc_info=True)
    return redirect(url_for('operacional.lixeira'))

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
            return render_template("cadastro.html", mensagem=errors[0], form_data=request.form), 400

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
            preco_compra = preco_por_arroba(peso, val_arr) if (peso and val_arr) else None

            if animal_repository.check_brinco_exists(brinco, current_user.farm_id):
                return render_template("cadastro.html", mensagem="Brinco já existe."), 400

            new_id = animal_repository.cadastrar_animal(
                brinco, sexo, data_compra, preco_compra, peso, current_user.farm_id,
                data_nascimento=data_nascimento, raca=raca,
            )
            flash(f"Animal {brinco} cadastrado com sucesso.", 'success')
            return redirect(url_for('operacional.detalhes', id_animal=new_id))
        except _IntegrityError:
            # UNIQUE (brinco, user_id) conta linhas soft-deletadas, que
            # check_brinco_exists ignora — o brinco pode estar na lixeira.
            logger.warning("IntegrityError cadastro (brinco duplicado) user=%s", current_user.farm_id)
            return render_template(
                "cadastro.html",
                mensagem="Já existe um animal com esse brinco. Verifique a lixeira — ele pode estar excluído.",
                form_data=request.form), 400
        except Exception as e:
            logger.error(f"Erro cadastro: {e}", exc_info=True)
            msg = "Não foi possível cadastrar o animal. Tente novamente."
    return render_template("cadastro.html", mensagem=msg)

@operacional_bp.route('/animal/<int:id_animal>')
@login_required
def detalhes(id_animal):
    try:
        animal = animal_repository.get_animal_by_id(id_animal, current_user.farm_id)
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
        flash("Não foi possível carregar os dados do animal agora. Tente novamente.", 'error')
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

        # Carência sanitária: animal medicado dentro da janela não pode ir ao abate.
        # A trava é aqui e não no repositório porque é o override que precisa de
        # formulário — e o override só vale com registro de quem autorizou.
        confirmou = request.form.get('confirmar_carencia') == '1'
        try:
            carencias = sanitario_repository.get_carencias_ativas(
                current_user.farm_id, animal_ids=[id_animal])
        except Exception as e:
            logger.error(f"Erro checar carência: {e}", exc_info=True)
            carencias = []
        if carencias and not confirmou:
            return render_template('vender.html', id_animal=id_animal,
                                   carencias=carencias, form_data=request.form,
                                   mensagem=_msg_carencia(carencias)), 400

        try:
            dt = request.form['data_venda']
            peso = float(request.form['peso_venda'])
            val = float(request.form['valor_arroba'])
            ok = animal_repository.registrar_venda(id_animal, current_user.farm_id, dt, preco_por_arroba(peso, val), peso)
            if not ok:
                return render_template('vender.html', id_animal=id_animal,
                                       mensagem="Animal não encontrado."), 404
            if carencias:
                sanitario_repository.registrar_override_carencia(carencias, current_user.farm_id)
                flash("Venda autorizada dentro da carência — registrado para auditoria.", 'warning')
            return redirect(url_for('operacional.detalhes', id_animal=id_animal))
        except Exception as e:
            logger.error(f"Erro vender: {e}", exc_info=True)
            return render_template('vender.html', id_animal=id_animal,
                                   mensagem="Não foi possível registrar. Tente novamente."), 400
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
            animais = animal_repository.get_animais_ativos_com_ultimo_peso(current_user.farm_id)
            restore_data = {
                'animal_ids': request.form.getlist('animal_ids[]'),
                'pesos_venda': request.form.getlist('pesos_venda[]'),
            }
            return render_template('venda_lote.html', animais=animais, erro=errors[0],
                                   form_data=request.form, restore_data=restore_data), 400

        animal_ids = request.form.getlist('animal_ids[]')
        pesos = request.form.getlist('pesos_venda[]')

        if not animal_ids:
            animais = animal_repository.get_animais_ativos_com_ultimo_peso(current_user.farm_id)
            return render_template('venda_lote.html', animais=animais,
                                   erro="Selecione pelo menos um animal."), 400

        confirmou = request.form.get('confirmar_carencia') == '1'
        try:
            carencias = sanitario_repository.get_carencias_ativas(
                current_user.farm_id, animal_ids=animal_ids)
        except Exception as e:
            logger.error(f"Erro checar carência (lote): {e}", exc_info=True)
            carencias = []
        if carencias and not confirmou:
            animais = animal_repository.get_animais_ativos_com_ultimo_peso(current_user.farm_id)
            restore_data = {
                'animal_ids': animal_ids,
                'pesos_venda': pesos,
            }
            return render_template('venda_lote.html', animais=animais,
                                   erro=_msg_carencia(carencias), carencias=carencias,
                                   form_data=request.form, restore_data=restore_data), 400

        data_venda = request.form['data_venda']
        valor_arroba = float(request.form['valor_arroba'])

        vendas = []
        for aid_str, peso_str in zip(animal_ids, pesos):
            try:
                aid = int(aid_str)
                peso = float(peso_str)
                if peso <= 0:
                    raise ValueError
                vendas.append((aid, peso, preco_por_arroba(peso, valor_arroba)))
            except (ValueError, TypeError):
                animais = animal_repository.get_animais_ativos_com_ultimo_peso(current_user.farm_id)
                return render_template('venda_lote.html', animais=animais,
                                       erro="Peso inválido em um ou mais animais."), 400

        try:
            vendidos, invalidos = animal_repository.registrar_venda_lote(vendas, current_user.farm_id, data_venda)
        except Exception as e:
            logger.error(f"Erro venda lote: {e}", exc_info=True)
            animais = animal_repository.get_animais_ativos_com_ultimo_peso(current_user.farm_id)
            return render_template('venda_lote.html', animais=animais,
                                   erro="Erro ao registrar venda. Tente novamente."), 400

        if carencias:
            vendidos_ids = {aid for aid, _, _ in vendas if aid not in set(invalidos)}
            sanitario_repository.registrar_override_carencia(
                [c for c in carencias if c[0] in vendidos_ids], current_user.farm_id)
            flash("Venda autorizada dentro da carência — registrado para auditoria.", 'warning')

        msg = f"{vendidos} animal(is) vendido(s) com sucesso."
        if invalidos:
            msg += f" {len(invalidos)} ignorado(s) (já vendido ou não pertence ao usuário)."
        flash(msg, 'success')
        return redirect(url_for('operacional.painel'))

    animais = animal_repository.get_animais_ativos_com_ultimo_peso(current_user.farm_id)
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
            ('dias_carencia',  {'required': False, 'type': 'int',  'min_val': 0, 'max_val': 365, 'label': 'Dias de carência'}),
        ])
        if errors:
            return render_template('medicar.html', id_animal=id_animal, mensagem=errors[0]), 400
        try:
            ok = animal_repository.registrar_medicacao(
                id_animal, current_user.farm_id,
                request.form['data_aplicacao'], request.form['nome'],
                request.form['custo'], request.form['obs'],
                dias_carencia=_dias_carencia_do_form(request.form)
            )
            if not ok:
                return render_template('medicar.html', id_animal=id_animal,
                                       mensagem="Animal não encontrado."), 404
            return redirect(url_for('operacional.detalhes', id_animal=id_animal))
        except Exception as e:
            logger.error(f"Erro medicar: {e}", exc_info=True)
            return render_template('medicar.html', id_animal=id_animal,
                                   mensagem="Não foi possível registrar. Tente novamente."), 400
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
            ok = animal_repository.registrar_pesagem(
                id_animal, current_user.farm_id,
                request.form['data_pesagem'], request.form['peso']
            )
            if not ok:
                return render_template('nova_pesagem.html', id_animal=id_animal,
                                       mensagem="Animal não encontrado."), 404
            return redirect(url_for('operacional.detalhes', id_animal=id_animal))
        except Exception as e:
            logger.error(f"Erro pesar: {e}", exc_info=True)
            return render_template('nova_pesagem.html', id_animal=id_animal,
                                   mensagem="Não foi possível registrar. Tente novamente."), 400
    return render_template('nova_pesagem.html', id_animal=id_animal)

@operacional_bp.route('/excluir_animal/<int:id_animal>', methods=['POST'])
@login_required
def excluir_animal(id_animal):
    try:
        animal_repository.soft_delete_animal(id_animal, current_user.farm_id)
    except Exception as e:
        logger.error(f"Erro excluir: {e}", exc_info=True)
    return redirect(url_for('operacional.painel'))

@operacional_bp.route('/excluir_pesagem/<int:id_pesagem>', methods=['POST'])
@login_required
def excluir_pesagem(id_pesagem):
    aid = None
    try:
        aid = animal_repository.soft_delete_pesagem(id_pesagem, current_user.farm_id)
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
                ('dias_carencia',  {'required': False, 'type': 'int',  'min_val': 0, 'max_val': 365, 'label': 'Dias de carência'}),
            ])
            if errors:
                lista_animais = animal_repository.get_animais_ativos(current_user.farm_id)
                return render_template('vacinacao_lote.html', erro=errors[0], animais=lista_animais), 400

            animal_repository.insert_medicacao_lote(
                animais_ids,
                request.form['data_aplicacao'],
                request.form['nome'],
                request.form['custo'],
                request.form['obs'],
                user_id=current_user.farm_id,
                dias_carencia=_dias_carencia_do_form(request.form),
            )
            flash(f"{len(animais_ids)} animal(is) vacinado(s) com sucesso.", 'success')
            return redirect(url_for('operacional.vacinacao_coletiva'))
        except Exception as e:
            logger.error(f"Erro vacinacao lote: {e}", exc_info=True)
            lista_animais = animal_repository.get_animais_ativos(current_user.farm_id)
            return render_template('vacinacao_lote.html', erro="Erro interno ao processar vacinação.", animais=lista_animais), 500

    try:
        lista_animais = animal_repository.get_animais_ativos(current_user.farm_id)
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
                (brinco, sexo, float(peso_txt), preco_por_arroba(float(peso_txt), valor_arroba))
                for brinco, sexo, peso_txt in zip(brincos, sexos, pesos_str)
            ]

            animal_repository.cadastrar_lote(
                current_user.farm_id, codigo_lote, descricao, data_compra, animais_data, raca=raca
            )
            flash(f"Lote '{codigo_lote}' salvo com {len(brincos)} animais e pesos individuais!", 'success')
            # ponytail: painel/get_animais_paginados não têm filtro por lote_id (fora do escopo
            # deste arquivo alterar animal_repository.py) — reaproveita o filtro `busca` existente,
            # já que os brincos do lote seguem a convenção "{codigo_lote}-NN".
            return redirect(url_for('operacional.painel', busca=codigo_lote))
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
    erro_geral = None

    try:
        lotes = animal_repository.get_lotes(current_user.farm_id)

        if request.method == 'POST':
            animal_ids = request.form.getlist('animal_ids[]')
            pesos = request.form.getlist('pesos[]')

            if not animal_ids:
                animais = animal_repository.get_animais_ativos_por_lote(current_user.farm_id, lote_id)
                return render_template('pesagem_lote.html', lotes=lotes, animais=animais,
                                       lote_id_selecionado=lote_id,
                                       erro="Selecione pelo menos um animal."), 400

            errors = validate(request.form, [
                ('data_pesagem', {'required': True, 'type': 'date', 'label': 'Data da pesagem'}),
            ])
            if errors:
                animais = animal_repository.get_animais_ativos_por_lote(current_user.farm_id, lote_id)
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
                    animais = animal_repository.get_animais_ativos_por_lote(current_user.farm_id, lote_id)
                    return render_template('pesagem_lote.html', lotes=lotes, animais=animais,
                                           lote_id_selecionado=lote_id,
                                           erro="Peso inválido em um ou mais animais."), 400

            inseridos, invalidos = animal_repository.registrar_pesagens_lote(
                pairs, current_user.farm_id, request.form['data_pesagem']
            )
            msg = f"{inseridos} pesagem(ns) registrada(s) com sucesso."
            if invalidos:
                msg += f" {len(invalidos)} animal(is) ignorado(s) (não pertence ao usuário)."
            flash(msg, 'success')
            return redirect(url_for('operacional.pesagem_lote', lote_id=lote_id))

        animais = animal_repository.get_animais_ativos_por_lote(current_user.farm_id, lote_id)
    except Exception as e:
        logger.error(f"Erro pesagem lote: {e}", exc_info=True)
        erro_geral = "Erro ao registrar pesagens. Tente novamente."

    return render_template('pesagem_lote.html', lotes=lotes, animais=animais,
                           lote_id_selecionado=lote_id, erro=erro_geral)


# ════════════════════════════════════════════════════════════════════════════
# HEREDITARIEDADE
# ════════════════════════════════════════════════════════════════════════════

@operacional_bp.route('/animais/<int:id_animal>/progenie')
@login_required
def progenie_animal(id_animal):
    animal = animal_repository.get_animal_by_id(id_animal, current_user.farm_id)
    if not animal:
        return redirect(url_for('operacional.painel'))
    filhos = animal_repository.get_progenie_by_touro(id_animal, current_user.farm_id)
    return render_template('animal_progenie.html', animal=animal, filhos=filhos)


@operacional_bp.route('/animais/<int:id_animal>/reproducao')
@login_required
def reproducao_animal(id_animal):
    animal = animal_repository.get_animal_by_id(id_animal, current_user.farm_id)
    if not animal:
        return redirect(url_for('operacional.painel'))
    eventos          = reproducao_repository.get_reproducao_by_vaca(id_animal, current_user.farm_id)
    stats            = animal_repository.get_historico_reproducao(id_animal, current_user.farm_id)
    machos           = animal_repository.get_animais_ativos_por_sexo(current_user.farm_id, 'M')
    partos_previstos = []
    try:
        partos_previstos = reproducao_repository.get_partos_previstos(current_user.farm_id, dias=60)
    except Exception:
        pass
    return render_template('animal_reproducao.html',
                           animal=animal, eventos=eventos,
                           stats=stats, machos=machos,
                           partos_previstos=partos_previstos)


@operacional_bp.route('/reproducao')
@login_required
def reproducao_painel():
    """Visão de rebanho da reprodução — /animais/<id>/reproducao só responde por indivíduo.

    A gestação bovina é ~285 dias, então esse horizonte cobre toda vaca gestante:
    vw_partos_previstos já filtra DG positivo com parto ainda não registrado.
    """
    partos_previstos, total_gestantes = [], 0
    try:
        partos_previstos = reproducao_repository.get_partos_previstos(current_user.farm_id, dias=285)
        total_gestantes = reproducao_repository.get_contagem_gestantes(current_user.farm_id)
    except Exception as e:
        logger.error(f"Erro painel reprodução: {e}", exc_info=True)
        flash("Não foi possível carregar os dados de reprodução agora. Tente novamente em instantes.", 'error')

    # dias_restantes (p[4]) é negativo quando a data prevista já passou sem parto registrado.
    n_atrasados = sum(1 for p in partos_previstos if p[4] <= 0)
    n_proximos_30 = sum(1 for p in partos_previstos if 0 < p[4] <= 30)

    return render_template('reproducao_painel.html',
                           partos_previstos=partos_previstos,
                           total_gestantes=total_gestantes,
                           n_atrasados=n_atrasados,
                           n_proximos_30=n_proximos_30)


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
            if not animal_repository.get_animal_by_id(_tid, current_user.farm_id):
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

    if not id_animal or not animal_repository.get_animal_by_id(id_animal, current_user.farm_id):
        return redirect(url_for('operacional.painel'))

    if erros:
        for e in erros:
            flash(e, 'error')
        return redirect(url_for('operacional.reproducao_animal', id_animal=id_animal))

    criar_bezerro = (resultado == 'vivo' and data_parto and brinco_bezerro and sexo_bezerro
                     and not animal_repository.check_brinco_exists(brinco_bezerro, current_user.farm_id))

    _, bezerro_id = reproducao_repository.registrar_parto_com_bezerro(
        current_user.farm_id,
        id_animal,
        int(touro_id_raw) if touro_id_raw else None,
        touro_externo,
        request.form.get('data_cobertura'),
        data_parto,
        resultado,
        brinco_bezerro=brinco_bezerro if criar_bezerro else None,
        sexo_bezerro=sexo_bezerro if criar_bezerro else None,
    )

    bezerro_msg = ''
    if resultado == 'vivo' and data_parto and brinco_bezerro and sexo_bezerro:
        if bezerro_id:
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

    if erros:
        for e in erros:
            flash(e, 'error')
    else:
        try:
            reproducao_repository.update_diagnostico(
                rep_id,
                current_user.farm_id,
                request.form.get('diagnostico'),
                request.form.get('data_diagnostico'),
            )
            flash('Diagnóstico registrado com sucesso.', 'success')
        except Exception as e:
            logger.error(f"Erro DG {rep_id}: {e}", exc_info=True)
            flash('Erro ao registrar diagnóstico.', 'error')

    id_animal = reproducao_repository.get_vaca_id_by_reproducao(rep_id, current_user.farm_id)
    if id_animal:
        return redirect(url_for('operacional.reproducao_animal', id_animal=id_animal))
    return redirect(url_for('operacional.painel'))


@operacional_bp.route('/rebanho/ranking-touros')
@login_required
def ranking_touros():
    try:
        ranking = animal_repository.get_ranking_touros(current_user.farm_id)
        gmd_medio_raw = animal_repository.get_gmd_medio_rebanho(current_user.farm_id)

        # Converte o valor retornado para Decimal, ou usa Decimal('0.0') se vier vazio/None
        gmd_medio = Decimal(str(gmd_medio_raw)) if gmd_medio_raw else Decimal('0.0')

    except Exception:
        logger.exception("Erro em ranking_touros user_id=%s", current_user.farm_id)
        # Substitui o 0.0 (float) por Decimal('0.0') no fallback do erro
        ranking, gmd_medio = [], Decimal('0.0')
        
    return render_template('ranking_touros.html', ranking=ranking, gmd_medio=gmd_medio)

_CSV_COLUNAS_OBRIGATORIAS = {'brinco', 'sexo', 'data_compra', 'peso_kg', 'valor_arroba'}
_CSV_MAX_BYTES = 1 * 1024 * 1024  # 1 MB
_CSV_MAX_LINHAS = 5000
_CSV_CHUNK_SIZE = 500


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
                (current_user.farm_id,)
            )
            brincos_existentes = {row[0] for row in cursor.fetchall()}
            linhas_validas = []  # (linha, brinco, sexo, raca, data_compra, data_nasc, preco_compra)

            for i, row in enumerate(reader, start=2):
                if i - 1 > _CSV_MAX_LINHAS:
                    erros.append({'linha': i, 'msg': 'Limite de 5000 linhas atingido — importação interrompida.'})
                    break

                brinco      = (row.get('brinco') or '').strip()
                sexo        = (row.get('sexo') or '').strip().upper()
                data_compra = (row.get('data_compra') or '').strip()
                raca        = animal_repository._normalizar_raca(row.get('raca'))
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
                    preco_compra = preco_por_arroba(peso, arr)
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

                brincos_existentes.add(brinco)
                linhas_validas.append((i, brinco, sexo, raca, data_compra or None,
                                        data_nasc or None, preco_compra, peso))

            # brincos efetivamente inseridos, com a data e o peso da pesagem de
            # baseline (mesma transação): sem essa pesagem inicial o GMD nunca
            # é calculável, mesmo após novas pesagens. data_pesagem usa
            # data_compra ou, para nascidos na fazenda, data_nascimento.
            inseridos_pesagem = []

            # Insere em chunks via executemany — muito mais rápido que 1 INSERT
            # por linha. Se um chunk falhar (ex.: duas linhas do próprio CSV com
            # o mesmo brinco, que o set em memória não pega porque nenhuma das
            # duas foi inserida ainda), refaz esse chunk linha a linha só para
            # isolar e reportar qual(is) linha(s) conflitam.
            #
            # No Postgres um erro aborta a transação inteira: cada tentativa passível
            # de conflito roda dentro de um SAVEPOINT (conn.transaction()) para que
            # o rollback seja local e a importação prossiga.
            conn = cursor.connection
            for inicio in range(0, len(linhas_validas), _CSV_CHUNK_SIZE):
                chunk = linhas_validas[inicio:inicio + _CSV_CHUNK_SIZE]
                try:
                    with conn.transaction():
                        cursor.executemany(
                            "INSERT INTO animais (brinco, sexo, raca, data_compra, data_nascimento, "
                            "preco_compra, user_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                            [(brinco, sexo, raca, data_compra, data_nasc, preco_compra, current_user.farm_id)
                             for _, brinco, sexo, raca, data_compra, data_nasc, preco_compra, peso in chunk]
                        )
                    inseridos += len(chunk)
                    inseridos_pesagem += [(brinco, data_compra or data_nasc, peso)
                                          for _, brinco, sexo, raca, data_compra, data_nasc, preco_compra, peso in chunk]
                except _IntegrityError:
                    for linha, brinco, sexo, raca, data_compra, data_nasc, preco_compra, peso in chunk:
                        try:
                            with conn.transaction():
                                cursor.execute(
                                    "INSERT INTO animais (brinco, sexo, raca, data_compra, data_nascimento, "
                                    "preco_compra, user_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                                    (brinco, sexo, raca, data_compra, data_nasc, preco_compra, current_user.farm_id)
                                )
                            inseridos += 1
                            inseridos_pesagem.append((brinco, data_compra or data_nasc, peso))
                        except _IntegrityError:
                            erros.append({'linha': linha, 'msg': f"brinco '{brinco}' já existe (conflito)"})

            # Reconsulta os ids recém-criados por brinco (executemany não dá
            # lastrowid por linha) e grava as pesagens iniciais — mesmo padrão
            # de cadastrar_lote.
            if inseridos_pesagem:
                brincos = [brinco for brinco, _, _ in inseridos_pesagem]
                ph = ','.join(['%s'] * len(brincos))
                cursor.execute(
                    f"SELECT id, brinco FROM animais WHERE user_id = %s "
                    f"AND deleted_at IS NULL AND brinco IN ({ph})",
                    [current_user.farm_id] + brincos
                )
                id_por_brinco = {brinco: aid for aid, brinco in cursor.fetchall()}
                cursor.executemany(
                    "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)",
                    [(id_por_brinco[brinco], data_pesagem, peso)
                     for brinco, data_pesagem, peso in inseridos_pesagem if brinco in id_por_brinco]
                )

    except Exception as e:
        logger.error(f"Erro importação CSV: {e}", exc_info=True)
        return render_template('importar_csv.html',
                               erro="Erro interno ao processar importação. Verifique os dados e tente novamente.")

    return render_template('importar_csv.html',
                           resultado={'inseridos': inseridos, 'erros': erros})
