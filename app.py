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
from db_config import get_db_cursor # Necessário para o Context Processor

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

app = Flask(__name__)
# Pega a chave do .env 
app.secret_key = os.getenv('SECRET_KEY')

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
app.register_blueprint(config_bp)
app.register_blueprint(api_bp)

@app.context_processor
def inject_user_info():
    # Valor padrão caso não tenha nada configurado
    site_name = "Meu Rebanho"

    if current_user.is_authenticated:
        try:
            # Busca rápida apenas do nome para o cabeçalho
            with get_db_cursor() as cursor:
                cursor.execute("SELECT nome_fazenda FROM configuracoes WHERE user_id = %s", (current_user.id,))
                res = cursor.fetchone()
                if res and res[0]: # Se achou e não está vazio
                    site_name = res[0]
        except Exception:
            pass # Em caso de erro, mantém o padrão silenciosamente

    return {'nome_fazenda_header': site_name}

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