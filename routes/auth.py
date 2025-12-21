from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from db_config import get_db_cursor
from models import User
import logging

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('operacional.painel'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            with get_db_cursor() as cursor:
                cursor.execute("SELECT id, username, password_hash FROM usuarios WHERE username = %s", (username,))
                dados = cursor.fetchone()
                
                if dados:
                    user_obj = User(dados[0], dados[1], dados[2])
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
            novo_user = request.form['username'].strip()
            nova_senha = request.form['password'].strip()
            if not novo_user or not nova_senha:
                 return render_template('novo_usuario.html', mensagem="Preencha tudo.")

            with get_db_cursor() as cursor:
                cursor.execute("SELECT id FROM usuarios WHERE username = %s", (novo_user,))
                if cursor.fetchone():
                    mensagem = f"Erro: Usuário '{novo_user}' já existe."
                else:
                    hash_s = generate_password_hash(nova_senha)
                    cursor.execute("INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)", (novo_user, hash_s))
                    mensagem = f"Sucesso! Usuário '{novo_user}' criado."
        except Exception as e:
            logger.error(f"Erro novo_usuario: {e}", exc_info=True)
            mensagem = f"Erro: {e}"
    return render_template('novo_usuario.html', mensagem=mensagem)