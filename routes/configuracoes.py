from flask import Blueprint, g, render_template, request, redirect, url_for, session, flash
from flask_login import login_required, current_user
import logging
import os
from repositories import animal_repository, configuracao_repository
from routes.validators import validate
from utils import plano as plano_regras

config_bp = Blueprint('configuracoes', __name__)
logger = logging.getLogger(__name__)


@config_bp.route('/configuracoes', methods=['GET', 'POST'])
@login_required
def settings():
    msg = None

    if request.method == 'POST':
        errors = validate(request.form, [
            ('nome_fazenda',  {'required': False, 'type': 'str',   'max_len': 255, 'label': 'Nome da fazenda'}),
            ('cidade_estado', {'required': False, 'type': 'str',   'max_len': 255, 'label': 'Cidade/Estado'}),
            ('area_total',    {'required': False, 'type': 'float', 'min_val': 0,   'label': 'Área total'}),
            ('gmd_meta',      {'required': False, 'type': 'float', 'min_val': 0.1, 'max_val': 5.0, 'label': 'GMD Meta (kg/dia)'}),
        ])
        if errors:
            dados_atuais = {}
            try:
                res = configuracao_repository.get_configuracao(current_user.farm_id)
                if res:
                    dados_atuais = {'nome_fazenda': res[0], 'cidade_estado': res[1], 'area_total': res[2],
                                    'gmd_meta': res[3] if res[3] is not None else 0.800}
            except Exception as e:
                logger.error(f"Erro ao carregar configurações: {e}", exc_info=True)
            dados_atuais.update({
                'nome_fazenda': request.form.get('nome_fazenda', dados_atuais.get('nome_fazenda', '')),
                'cidade_estado': request.form.get('cidade_estado', dados_atuais.get('cidade_estado', '')),
                'area_total': request.form.get('area_total', dados_atuais.get('area_total', '')),
                'gmd_meta': request.form.get('gmd_meta', dados_atuais.get('gmd_meta', 0.800)),
            })
            return render_template('configuracoes.html', config=dados_atuais, mensagem=errors[0]), 400
        try:
            nome = request.form.get('nome_fazenda', '').strip()
            cidade = request.form.get('cidade_estado', '').strip()
            area = request.form.get('area_total') or 0
            gmd_meta = request.form.get('gmd_meta') or 0.800

            configuracao_repository.upsert_configuracao(current_user.farm_id, nome, cidade, area, gmd_meta)
            session.pop('nome_fazenda', None)
            session.pop('gmd_meta', None)
            flash("Configurações salvas com sucesso!", 'success')
            return redirect(url_for('configuracoes.settings'))
        except Exception as e:
            logger.error(f"Erro ao salvar configurações: {e}", exc_info=True)
            flash("Erro ao salvar dados.", 'error')
            return redirect(url_for('configuracoes.settings'))

    dados_atuais = {}
    try:
        res = configuracao_repository.get_configuracao(current_user.farm_id)
        if res:
            dados_atuais = {'nome_fazenda': res[0], 'cidade_estado': res[1], 'area_total': res[2],
                            'gmd_meta': res[3] if res[3] is not None else 0.800}
    except Exception as e:
        logger.error(f"Erro ao carregar configurações: {e}", exc_info=True)

    return render_template('configuracoes.html', config=dados_atuais)


@config_bp.route('/plano')
@login_required
def plano():
    """Tela do plano: o que a fazenda tem hoje e como pagar.

    A ativação é manual neste estágio — o dono paga pelo link e a liberação é
    aplicada por fora (scripts/ativar_plano.py). A tela existe para que ele
    saiba o limite, quanto já usou e quando o trial vence; sem isso o limite
    aparece pela primeira vez como um erro no meio de um cadastro.
    """
    atual = getattr(g, 'plano', None) or plano_regras.PLANO_PADRAO
    cabecas = animal_repository.contar_cabecas_ativas(current_user.farm_id)
    return render_template(
        'plano.html',
        plano=plano_regras.resumo(atual, cabecas),
        link_pagamento=os.getenv('ASAAS_LINK_PAGAMENTO', ''),
    )
