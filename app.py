import os
import logging
import subprocess as _sp
from flask import Flask, redirect, url_for, render_template, session, request
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from extensions import limiter, scheduler, compress
from models import User
from routes.auth import auth_bp
from routes.financeiro import financeiro_bp
from routes.operacional import operacional_bp
from routes.api import api_bp
from routes.configuracoes import config_bp
from routes.pastos import pastos_bp
from routes.estoque import estoque_bp
from routes.sanitario import sanitario_bp
from repositories import configuracao_repository

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
csrf = CSRFProtect(app)
limiter.init_app(app)
compress.init_app(app)

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
app.register_blueprint(pastos_bp)
app.register_blueprint(estoque_bp)
app.register_blueprint(sanitario_bp)

@app.template_filter('brl')
def format_brl(value):
    try:
        return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00"


@app.context_processor
def inject_user_info():
    if not current_user.is_authenticated:
        return {'nome_fazenda_header': "Meu Rebanho"}

    cached = session.get('nome_fazenda')
    if cached is None:
        try:
            res = configuracao_repository.get_configuracao(current_user.id)
            cached = res[0] if (res and res[0]) else "Meu Rebanho"
        except Exception:
            cached = "Meu Rebanho"
        session['nome_fazenda'] = cached

    return {'nome_fazenda_header': cached}


@app.after_request
def set_static_cache(response):
    if request.path.startswith('/static/'):
        response.cache_control.max_age = 31536000
        response.cache_control.public = True
    return response

@app.after_request
def set_security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    return response


def _git_sha():
    try:
        return _sp.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'], stderr=_sp.DEVNULL
        ).decode().strip()
    except Exception:
        return '0'

_CACHE_BUST = _git_sha()

@app.context_processor
def inject_cache_bust():
    return {'cache_bust': _CACHE_BUST}

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('operacional.painel'))
    return render_template('landing.html')

# Em produção com Gunicorn + preload_app=True o scheduler inicia no processo master
# (antes do fork). Com preload_app=False cada worker importaria o módulo e iniciaria
# o scheduler individualmente — triplo disparo de emails. O guard abaixo cobre ambos
# os casos: no dev server usa WERKZEUG_RUN_MAIN; no Gunicorn usa SCHEDULER_ENABLED
# que gunicorn.conf.py seta como 'false' nos workers filhos (age > 1).
_sched_permitido = (
    os.environ.get('WERKZEUG_RUN_MAIN') == 'true'  # Flask dev server (reload)
    or (not app.debug and os.environ.get('SCHEDULER_ENABLED', 'true') != 'false')
)

if _sched_permitido:
    from utils.alertas import (
        verificar_contas_vencendo,
        verificar_protocolos_vencendo,
        verificar_estoque_critico,
        verificar_feedback_7dias,
    )
    scheduler.add_job(verificar_contas_vencendo,    'cron', hour=8, args=[app])
    scheduler.add_job(verificar_protocolos_vencendo,'cron', hour=8, args=[app])
    scheduler.add_job(verificar_estoque_critico,    'cron', day_of_week='mon', hour=8, args=[app])
    scheduler.add_job(verificar_feedback_7dias,     'cron', hour=9, args=[app])
    scheduler.start()

if __name__ == '__main__':
    
    porta = int(os.getenv('PORT', 5000))
    modo_debug = os.getenv('FLASK_DEBUG', 'False') == 'True'
    
    print(f"🚀 Servidor rodando! Acesse: http://192.168.2.137:{porta}")
    app.run(host='0.0.0.0', port=porta, debug=modo_debug)