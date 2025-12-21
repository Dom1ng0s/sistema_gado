import os
import logging
from flask import Flask, redirect, url_for
from flask_login import LoginManager, current_user
from models import User
from routes.auth import auth_bp
from routes.financeiro import financeiro_bp
from routes.operacional import operacional_bp
from routes.api import api_bp

# Configuração
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'chave_segura')

# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login' # Prefixo do Blueprint!

@login_manager.user_loader
def load_user(user_id):
    return User.get_user_id(user_id)

# Registro de Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(financeiro_bp)
app.register_blueprint(operacional_bp)
app.register_blueprint(api_bp)

# Rota Raiz
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('operacional.painel'))
    return redirect(url_for('auth.login'))

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', 'False') == 'True')