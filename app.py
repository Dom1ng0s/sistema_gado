import os
import logging
from flask import Flask, redirect, url_for
from flask_login import LoginManager, current_user
from models import User
from routes.auth import auth_bp
from routes.financeiro import financeiro_bp
from routes.operacional import operacional_bp
from routes.api import api_bp

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

app = Flask(__name__)
# Pega a chave do .env ou usa uma padrão se não encontrar
app.secret_key = os.getenv('SECRET_KEY', 'chave_padrao_desenvolvimento')

# Configuração do Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return User.get_user_id(user_id)

# Registro das Rotas (Blueprints)
app.register_blueprint(auth_bp)
app.register_blueprint(financeiro_bp)
app.register_blueprint(operacional_bp)
app.register_blueprint(api_bp)

# Rota Principal (Redirecionamento Inteligente)
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('operacional.painel'))
    return redirect(url_for('auth.login'))

if __name__ == '__main__':
    # --- A MÁGICA ACONTECE AQUI ---
    # host='0.0.0.0' -> Libera o acesso para o Windows/Celular entrar no site
    # port=5000      -> Garante que vai rodar na porta que liberamos no CasaOS
    porta = int(os.getenv('PORT', 5000))
    modo_debug = os.getenv('FLASK_DEBUG', 'False') == 'True'
    
    print(f"🚀 Servidor rodando! Acesse: http://192.168.2.137:{porta}")
    app.run(host='0.0.0.0', port=porta, debug=modo_debug)