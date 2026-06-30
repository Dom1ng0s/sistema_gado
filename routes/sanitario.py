import logging
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from repositories import sanitario_repository
from routes.validators import validate

sanitario_bp = Blueprint('sanitario', __name__)
logger = logging.getLogger(__name__)


@sanitario_bp.route('/sanitario', methods=['GET', 'POST'])
@login_required
def lista_protocolos():
    mensagem = None

    if request.method == 'POST':
        errors = validate(request.form, [
            ('nome',              {'required': True,  'type': 'str',  'max_len': 200, 'label': 'Nome'}),
            ('intervalo_dias',    {'required': True,  'type': 'int',  'min_val': 1,   'label': 'Intervalo (dias)'}),
            ('proxima_aplicacao', {'required': True,  'type': 'date',                 'label': 'Próxima aplicação'}),
            ('descricao',         {'required': False, 'type': 'str',  'max_len': 500, 'label': 'Descrição'}),
        ])
        if errors:
            mensagem = ('erro', errors[0])
        else:
            try:
                sanitario_repository.insert_protocolo(
                    current_user.id,
                    request.form.get('nome').strip(),
                    request.form.get('descricao', '').strip() or None,
                    int(request.form.get('intervalo_dias')),
                    request.form.get('proxima_aplicacao'),
                )
                mensagem = ('sucesso', 'Protocolo cadastrado com sucesso.')
            except Exception as e:
                logger.error(f"Erro ao inserir protocolo: {e}", exc_info=True)
                mensagem = ('erro', 'Erro ao salvar protocolo. Tente novamente.')

    protocolos = []
    try:
        protocolos = sanitario_repository.get_protocolos(current_user.id)
    except Exception as e:
        logger.error(f"Erro ao listar protocolos: {e}", exc_info=True)
        mensagem = ('erro', 'Erro ao carregar protocolos. Execute init_db.py.')

    return render_template('sanitario_lista.html', protocolos=protocolos, mensagem=mensagem)


@sanitario_bp.route('/sanitario/<int:protocolo_id>/aplicar', methods=['POST'])
@login_required
def aplicar_protocolo(protocolo_id):
    try:
        nome = sanitario_repository.registrar_aplicacao(protocolo_id, current_user.id)
        if nome is None:
            return redirect(url_for('sanitario.lista_protocolos'))
        return redirect(url_for('operacional.vacinacao_coletiva', protocolo=nome))
    except Exception as e:
        logger.error(f"Erro ao aplicar protocolo {protocolo_id}: {e}", exc_info=True)
        return redirect(url_for('sanitario.lista_protocolos'))


@sanitario_bp.route('/sanitario/<int:protocolo_id>/desativar', methods=['POST'])
@login_required
def desativar_protocolo(protocolo_id):
    try:
        sanitario_repository.desativar_protocolo(protocolo_id, current_user.id)
    except Exception as e:
        logger.error(f"Erro ao desativar protocolo {protocolo_id}: {e}", exc_info=True)
    return redirect(url_for('sanitario.lista_protocolos'))
