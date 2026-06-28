from flask import Blueprint, render_template, request, session
from flask_login import login_required, current_user
import logging
from repositories import configuracao_repository
from routes.validators import validate

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
        ])
        if errors:
            return render_template('configuracoes.html', config={}, mensagem=errors[0]), 400
        try:
            nome = request.form.get('nome_fazenda', '').strip()
            cidade = request.form.get('cidade_estado', '').strip()
            area = request.form.get('area_total') or 0

            configuracao_repository.upsert_configuracao(current_user.id, nome, cidade, area)
            session.pop('nome_fazenda', None)
            msg = "Configurações salvas com sucesso!"
        except Exception as e:
            logger.error(f"Erro ao salvar configurações: {e}", exc_info=True)
            msg = "Erro ao salvar dados."

    dados_atuais = {}
    try:
        res = configuracao_repository.get_configuracao(current_user.id)
        if res:
            dados_atuais = {'nome': res[0], 'cidade': res[1], 'area': res[2]}
    except Exception as e:
        logger.error(f"Erro ao carregar configurações: {e}", exc_info=True)

    return render_template('configuracoes.html', config=dados_atuais, mensagem=msg)
