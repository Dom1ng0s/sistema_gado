import secrets
import logging
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from db_config import get_db_cursor
from extensions import limiter
from models import User
from repositories import auth_repository
from routes.validators import validate
from utils.email_service import send_reset_code, send_welcome_email

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('operacional.painel'))

    if request.method == 'POST':
        errors = validate(request.form, [
            ('username', {'required': True, 'type': 'str', 'max_len': 150, 'label': 'Usuário'}),
            ('password', {'required': True, 'type': 'str', 'max_len': 255, 'label': 'Senha'}),
        ])
        if errors:
            return render_template('login.html', mensagem=errors[0]), 400

        username = request.form['username']
        password = request.form['password']

        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    "SELECT id, username, password_hash, email FROM usuarios WHERE username = %s OR email = %s",
                    (username, username)
                )
                dados = cursor.fetchone()

                if dados:
                    user_obj = User(dados[0], dados[1], dados[2], dados[3])
                    if check_password_hash(user_obj.password_hash, password):
                        login_user(user_obj)
                        return redirect(url_for('operacional.painel'))
        except Exception as e:
            logger.error(f"Erro login: {e}", exc_info=True)

        return render_template('login.html', mensagem="Usuário ou senha incorretos")
    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@auth_bp.route('/novo_usuario', methods=['GET', 'POST'])
def novo_usuario():
    mensagem = None
    if request.method == 'POST':
        try:
            errors = validate(request.form, [
                ('username',    {'required': True,  'type': 'str',   'max_len': 150, 'label': 'Usuário'}),
                ('password',    {'required': True,  'type': 'str',   'min_len': 6, 'max_len': 255, 'label': 'Senha'}),
                ('nome_fazenda',{'required': False, 'type': 'str',   'max_len': 255, 'label': 'Nome da fazenda'}),
                ('area_total',  {'required': False, 'type': 'float', 'min_val': 0,   'label': 'Área total'}),
            ])
            if errors:
                return render_template('novo_usuario.html', mensagem=errors[0]), 400

            novo_user  = request.form['username'].strip()
            nova_senha = request.form['password'].strip()
            email      = request.form.get('email', '').strip().lower()
            nome_fazenda = request.form.get('nome_fazenda', '').strip()
            cidade     = request.form.get('cidade_estado', '').strip()
            area       = request.form.get('area_total') or 0

            if not email:
                return render_template('novo_usuario.html', mensagem="Email é obrigatório."), 400

            if '@' not in email or '.' not in email.split('@')[-1]:
                return render_template('novo_usuario.html', mensagem="Email inválido."), 400

            with get_db_cursor() as cursor:
                cursor.execute("SELECT id FROM usuarios WHERE username = %s", (novo_user,))
                if cursor.fetchone():
                    mensagem = f"Usuário '{novo_user}' já existe."
                    return render_template('novo_usuario.html', mensagem=mensagem), 400

                cursor.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
                if cursor.fetchone():
                    return render_template('novo_usuario.html', mensagem="Este email já está cadastrado."), 400

                hash_s = generate_password_hash(nova_senha)
                cursor.execute(
                    "INSERT INTO usuarios (username, password_hash, email) VALUES (%s, %s, %s)",
                    (novo_user, hash_s, email)
                )
                user_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO configuracoes (user_id, nome_fazenda, cidade_estado, area_total) VALUES (%s, %s, %s, %s)",
                    (user_id, nome_fazenda, cidade, area)
                )

            try:
                send_welcome_email(email, novo_user)
            except Exception as mail_err:
                logger.warning(f"Email de boas-vindas não enviado para {email}: {mail_err}")

            return redirect(url_for('auth.login'))

        except Exception as e:
            logger.error(f"Erro novo_usuario: {e}", exc_info=True)
            mensagem = f"Erro ao criar conta: {e}"

    return render_template('novo_usuario.html', mensagem=mensagem)


# ─── Recuperação de Senha ────────────────────────────────────────────────────

@auth_bp.route('/esqueci_senha', methods=['GET', 'POST'])
@limiter.limit("5/hour")
def esqueci_senha():
    if current_user.is_authenticated:
        return redirect(url_for('operacional.painel'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email:
            return render_template('esqueci_senha.html', mensagem="Informe o email.")

        try:
            user = auth_repository.get_user_by_email(email)

            if user:
                code = str(secrets.randbelow(900000) + 100000)
                expires_at = datetime.utcnow() + timedelta(minutes=15)
                auth_repository.save_reset_token(user[0], code, expires_at)

                try:
                    send_reset_code(email, code)
                except Exception as e:
                    logger.error(f"Erro ao enviar email reset: {e}", exc_info=True)
                    return render_template('esqueci_senha.html',
                                           mensagem="Erro ao enviar email. Verifique a configuração de email.")

                session['reset_email'] = email
                session['reset_expires_at'] = expires_at.timestamp()

            # Resposta idêntica independente do email existir ou não
            return redirect(url_for('auth.verificar_codigo'))

        except Exception as e:
            logger.error(f"Erro esqueci_senha: {e}", exc_info=True)
            return render_template('esqueci_senha.html', mensagem="Erro interno. Tente novamente.")

    return render_template('esqueci_senha.html')


@auth_bp.route('/verificar_codigo', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=["POST"])
def verificar_codigo():
    email = session.get('reset_email')
    if not email:
        return redirect(url_for('auth.esqueci_senha'))

    expires_ts = session.get('reset_expires_at', 0)
    expires_in_seconds = max(0, int(expires_ts - datetime.utcnow().timestamp()))
    email_mascarado = _mascara_email(email)

    if request.method == 'POST':
        codigo = request.form.get('codigo', '').strip()

        try:
            token = auth_repository.get_valid_token(email, codigo)
        except Exception as e:
            logger.error(f"Erro verificar_codigo: {e}", exc_info=True)
            return render_template('verificar_codigo.html',
                                   mensagem="Erro interno. Tente novamente.",
                                   email_mascarado=email_mascarado,
                                   expires_in_seconds=expires_in_seconds)

        if not token:
            return render_template('verificar_codigo.html',
                                   mensagem="Código inválido ou expirado.",
                                   email_mascarado=email_mascarado,
                                   expires_in_seconds=expires_in_seconds)

        auth_repository.mark_token_used(token[0])
        session.pop('reset_email', None)
        session.pop('reset_expires_at', None)
        session['reset_verified'] = True
        session['reset_user_id'] = token[1]
        return redirect(url_for('auth.nova_senha'))

    return render_template('verificar_codigo.html',
                           email_mascarado=email_mascarado,
                           expires_in_seconds=expires_in_seconds)


@auth_bp.route('/reenviar-codigo', methods=['POST'])
@limiter.limit("5/hour")
def reenviar_codigo():
    email = session.get('reset_email')
    if not email:
        return redirect(url_for('auth.esqueci_senha'))

    try:
        user = auth_repository.get_user_by_email(email)
        if user:
            code = str(secrets.randbelow(900000) + 100000)
            expires_at = datetime.utcnow() + timedelta(minutes=15)
            auth_repository.save_reset_token(user[0], code, expires_at)
            try:
                send_reset_code(email, code)
            except Exception as e:
                logger.error(f"Erro reenvio email reset: {e}", exc_info=True)
                flash('Erro ao reenviar email. Verifique a configuração de email.', 'error')
                return redirect(url_for('auth.verificar_codigo'))

            session['reset_expires_at'] = expires_at.timestamp()
            flash('Novo código enviado. Verifique seu email.', 'success')
        else:
            flash('Email não encontrado.', 'error')
    except Exception as e:
        logger.error(f"Erro reenviar_codigo: {e}", exc_info=True)
        flash('Erro interno. Tente novamente.', 'error')

    return redirect(url_for('auth.verificar_codigo'))


@auth_bp.route('/nova_senha', methods=['GET', 'POST'])
def nova_senha():
    if not session.get('reset_verified') or not session.get('reset_user_id'):
        return redirect(url_for('auth.esqueci_senha'))

    if request.method == 'POST':
        nova = request.form.get('password', '').strip()
        confirma = request.form.get('password_confirm', '').strip()

        if len(nova) < 6:
            return render_template('nova_senha.html',
                                   mensagem="A senha deve ter pelo menos 6 caracteres.")
        if nova != confirma:
            return render_template('nova_senha.html', mensagem="As senhas não coincidem.")

        try:
            auth_repository.update_password(session['reset_user_id'], generate_password_hash(nova))
            session.pop('reset_verified', None)
            session.pop('reset_user_id', None)
            flash('Senha redefinida com sucesso! Faça login.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            logger.error(f"Erro nova_senha: {e}", exc_info=True)
            return render_template('nova_senha.html', mensagem="Erro ao salvar a senha. Tente novamente.")

    return render_template('nova_senha.html')


@auth_bp.route('/conta/apagar', methods=['POST'])
@login_required
def apagar_conta():
    confirmacao = request.form.get('confirmacao', '').strip()
    if confirmacao != current_user.username:
        flash('Confirmação incorreta. Digite seu nome de usuário exatamente.', 'error')
        return redirect(url_for('configuracoes.settings'))

    user_id = current_user.id
    try:
        logout_user()
        session.clear()
        with get_db_cursor() as cursor:
            cursor.execute("DELETE FROM usuarios WHERE id = %s", (user_id,))
        flash('Conta excluída com sucesso.', 'success')
    except Exception as e:
        logger.error(f"Erro ao apagar conta user_id={user_id}: {e}", exc_info=True)
        flash('Erro ao excluir a conta. Tente novamente.', 'error')

    return redirect(url_for('auth.login'))


def _mascara_email(email: str) -> str:
    try:
        user, domain = email.split('@', 1)
        return user[0] + ('*' * min(len(user) - 1, 4)) + '@' + domain
    except Exception:
        return '***'
