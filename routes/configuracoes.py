from flask import Blueprint, g, render_template, request, redirect, url_for, session, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta, timezone
import logging
import os
import secrets
from extensions import limiter
from repositories import (acesso_repository, animal_repository, auth_repository,
                          configuracao_repository)
from routes.validators import validate
from utils import plano as plano_regras
from utils.email_service import send_invite_code

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


@config_bp.route('/acessos', methods=['GET', 'POST'])
@login_required
@limiter.limit("20 per hour", methods=["POST"])
def acessos():
    """Quem entra nesta fazenda, e o convite por email.

    O convite não pede senha nem cria nada que o dono precise repassar: a
    primeira senha vem pelo código de `password_reset_tokens`, o mesmo fluxo de
    "esqueci minha senha", que já existe com código e expiração.
    """
    farm_id = current_user.farm_id
    msg, erro = None, None

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        papel = request.form.get('papel', '').strip()

        if '@' not in email or '.' not in email.split('@')[-1]:
            erro = "Informe um email válido."
        elif papel not in acesso_repository.PAPEIS_CONVIDAVEIS:
            erro = "Escolha um papel válido."

        if not erro:
            try:
                existente = auth_repository.get_user_by_email(email)
                if existente and existente[0] == farm_id:
                    erro = "Este email é o seu — você já é o dono da fazenda."
                else:
                    if existente:
                        account_id, codigo, username = existente[0], None, existente[1]
                    else:
                        config = configuracao_repository.get_configuracao(farm_id)
                        nome_fazenda = (config[0] if config and config[0] else 'fazenda')
                        username = acesso_repository.gerar_username(nome_fazenda, email)
                        # Senha aleatória que ninguém conhece: quem entra, entra
                        # pelo código enviado por email.
                        account_id = acesso_repository.criar_convidado(
                            username, email,
                            generate_password_hash(secrets.token_urlsafe(32)))
                        codigo = str(secrets.randbelow(900000) + 100000)
                        auth_repository.save_reset_token(
                            account_id, codigo,
                            datetime.now(timezone.utc) + timedelta(minutes=15))

                    acesso_repository.conceder(account_id, farm_id, papel)
                    msg = f"Acesso liberado para {email} como {papel}."
                    if not _avisar_convidado(email, farm_id, papel, codigo, username):
                        # O acesso já vale; o que falhou foi o aviso. O dono
                        # precisa saber, senão fica esperando alguém que nunca
                        # recebeu o código.
                        msg += (" O email não saiu — peça para a pessoa entrar "
                                "por 'Esqueci minha senha' com esse email.")
            except Exception as e:
                logger.error(f"Erro ao convidar {email}: {e}", exc_info=True)
                erro = "Não foi possível liberar o acesso. Tente novamente."

    return render_template('acessos.html',
                           acessos=acesso_repository.listar_por_fazenda(farm_id),
                           papeis=acesso_repository.PAPEIS_CONVIDAVEIS,
                           mensagem=msg, erro=erro)


def _avisar_convidado(email, farm_id, papel, codigo, username):
    """Email de convite; True se saiu.

    Falha de SMTP não desfaz o acesso — ele já vale, e o convidado ainda pode
    entrar por "esqueci minha senha" com este email. Mas o dono tem de ficar
    sabendo.
    """
    try:
        config = configuracao_repository.get_configuracao(farm_id)
        nome_fazenda = (config[0] if config and config[0] else 'uma fazenda')
        send_invite_code(email, nome_fazenda, papel, codigo, username)
        return True
    except Exception as e:
        logger.warning(f"Convite não enviado para {email}: {e}")
        return False


@config_bp.route('/acessos/<int:acesso_id>/revogar', methods=['POST'])
@login_required
def revogar_acesso(acesso_id):
    # O id vem da URL: sem o dono no WHERE, trocar o número revogaria o acesso
    # de outra fazenda. Quem filtra é o repositório.
    if acesso_repository.revogar(acesso_id, current_user.farm_id):
        flash("Acesso revogado. Vale na próxima requisição da pessoa.", 'success')
    else:
        flash("Acesso não encontrado nesta fazenda.", 'error')
    return redirect(url_for('configuracoes.acessos'))
