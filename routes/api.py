from flask import Blueprint, jsonify, render_template
from flask_login import login_required, current_user
from db_config import get_db_cursor
import logging

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

@api_bp.route('/graficos')
@login_required
def graficos_page():
    return render_template('graficos.html')

@api_bp.route('/dados-graficos')
@login_required
def dados_graficos_api():
    try:
        with get_db_cursor() as cursor:
            uid = current_user.id
            cursor.execute("SELECT sexo, COUNT(*) FROM animais WHERE user_id = %s AND data_venda IS NULL GROUP BY sexo", (uid,))
            dados_sexo = {sexo: qtd for sexo, qtd in cursor.fetchall()}
            
            cursor.execute("SELECT p.peso FROM pesagens p INNER JOIN (SELECT animal_id, MAX(id) as m FROM pesagens GROUP BY animal_id) u ON p.id=u.m INNER JOIN animais a ON p.animal_id=a.id WHERE a.user_id=%s AND a.data_venda IS NULL", (uid,))
            pesos = cursor.fetchall()
            cat_peso = {'Menos de 10@': 0, '10@ a 15@': 0, '15@ a 20@': 0, 'Mais de 20@': 0}
            for (p_kg,) in pesos:
                p_arr = float(p_kg)/30
                if p_arr < 10: cat_peso['Menos de 10@'] += 1
                elif 10 <= p_arr < 15: cat_peso['10@ a 15@'] += 1
                elif 15 <= p_arr < 20: cat_peso['15@ a 20@'] += 1
                else: cat_peso['Mais de 20@'] += 1
                
            cursor.execute("SELECT AVG(v.gmd) FROM v_gmd_analitico v JOIN animais a ON v.animal_id=a.id WHERE v.user_id=%s AND a.data_venda IS NULL", (uid,))
            gmd = cursor.fetchone()[0]
            
            return jsonify({'sexo': dados_sexo, 'peso': cat_peso, 'gmd_medio': float(gmd) if gmd else 0.0}), 200
    except Exception as e:
        logger.error(f"Erro API: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500