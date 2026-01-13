import os
import logging
from flask import Flask, redirect, url_for
from flask_login import LoginManager, current_user
from models import User
from routes.auth import auth_bp
from routes.financeiro import financeiro_bp
from routes.operacional import operacional_bp
from routes.api import api_bp
from routes.configuracoes import config_bp
from db_config import get_db_cursor 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return User.get_user_id(user_id)

app.register_blueprint(auth_bp)
app.register_blueprint(financeiro_bp)
app.register_blueprint(operacional_bp)
app.register_blueprint(config_bp)
app.register_blueprint(api_bp)

@app.context_processor
def inject_user_info():
    site_name = "Meu Rebanho"

    if current_user.is_authenticated:
        try:
            with get_db_cursor() as cursor:
                cursor.execute("SELECT nome_fazenda FROM configuracoes WHERE user_id = %s", (current_user.id,))
                res = cursor.fetchone()
                if res and res[0]: 
                    site_name = res[0]
        except Exception:
            pass 

    return {'nome_fazenda_header': site_name}

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('operacional.painel'))
    return redirect(url_for('auth.login'))

if __name__ == '__main__':
    
    porta = int(os.getenv('PORT', 5000))
    modo_debug = os.getenv('FLASK_DEBUG', 'False') == 'True'
    
    print(f"🚀 Servidor rodando! Acesse: http://192.168.2.137:{porta}")
    app.run(host='0.0.0.0', port=porta, debug=modo_debug)