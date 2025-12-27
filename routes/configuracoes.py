from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from db_config import get_db_cursor
import logging

config_bp = Blueprint('configuracoes', __name__)
logger = logging.getLogger(__name__)

@config_bp.route('/configuracoes', methods=['GET', 'POST'])
@login_required
def settings():
    msg = None
    
    # 1. PROCESSAR SALVAMENTO (POST)
    if request.method == 'POST':
        try:
            nome = request.form.get('nome_fazenda', '').strip()
            cidade = request.form.get('cidade_estado', '').strip()
            area = request.form.get('area_total')
            
            # Tratamento básico de números
            if not area: area = 0
            
            with get_db_cursor() as cursor:
                # O comando ON DUPLICATE KEY UPDATE garante que:
                # Se não existir -> Cria. Se existir -> Atualiza.
                sql = """
                INSERT INTO configuracoes (user_id, nome_fazenda, cidade_estado, area_total)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                nome_fazenda = VALUES(nome_fazenda),
                cidade_estado = VALUES(cidade_estado),
                area_total = VALUES(area_total)
                """
                cursor.execute(sql, (current_user.id, nome, cidade, area))
                msg = "✅ Configurações salvas com sucesso!"
                
        except Exception as e:
            logger.error(f"Erro ao salvar configurações: {e}", exc_info=True)
            msg = "❌ Erro ao salvar dados."

    # 2. CARREGAR DADOS ATUAIS (GET)
    dados_atuais = {}
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT nome_fazenda, cidade_estado, area_total FROM configuracoes WHERE user_id = %s", (current_user.id,))
            res = cursor.fetchone()
            if res:
                dados_atuais = {'nome': res[0], 'cidade': res[1], 'area': res[2]}
    except Exception as e:
        logger.error(f"Erro ao carregar configurações: {e}", exc_info=True)

    return render_template('configuracoes.html', config=dados_atuais, mensagem=msg)