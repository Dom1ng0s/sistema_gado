from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from db_config import get_db_cursor
import math
import logging

operacional_bp = Blueprint('operacional', __name__)
logger = logging.getLogger(__name__)

@operacional_bp.route('/painel')
@login_required
def painel():
    animais, termo, status = [], request.args.get('busca', ''), request.args.get('status', 'todos')
    pg = request.args.get('page', 1, type=int)
    limit, offset = 20, (pg - 1) * 20
    total_pg = 1

    try:
        with get_db_cursor() as cursor:
            conds, params = ["user_id = %s"], [current_user.id]
            if termo: conds.append("brinco LIKE %s"); params.append(f"{termo}%")
            if status == 'ativos': conds.append("data_venda IS NULL")
            elif status == 'vendidos': conds.append("data_venda IS NOT NULL")
            
            where = " WHERE " + " AND ".join(conds)
            cursor.execute(f"SELECT COUNT(*) FROM animais {where}", tuple(params))
            total = cursor.fetchone()[0]
            
            cursor.execute(f"SELECT id, brinco, sexo, data_compra, preco_compra, data_venda, preco_venda FROM animais {where} ORDER BY LENGTH(brinco) ASC, brinco ASC LIMIT %s OFFSET %s", tuple(params + [limit, offset]))
            animais = cursor.fetchall()
            if total > 0: total_pg = math.ceil(total / limit)
    except Exception as e:
        logger.error(f"Erro painel: {e}", exc_info=True)
    
    return render_template("index.html", lista_animais=animais, pagina_atual=pg, total_paginas=total_pg, busca=termo, status=status)

@operacional_bp.route("/cadastro", methods=["GET", "POST"])
@login_required
def cadastro():
    msg = None
    if request.method == "POST":
        try:
            brinco, sexo, data = request.form["brinco"].strip(), request.form["sexo"], request.form["data_compra"]
            peso = float(request.form["peso_compra"])
            val_arr = float(request.form["valor_arroba"])
            
            with get_db_cursor() as cursor:
                cursor.execute("SELECT id FROM animais WHERE brinco = %s AND user_id = %s", (brinco, current_user.id))
                if cursor.fetchone(): return render_template("cadastro.html", mensagem="Brinco já existe.")
                
                cursor.execute("INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id) VALUES (%s, %s, %s, %s, %s)", (brinco, sexo, data, (peso/30)*val_arr, current_user.id))
                aid = cursor.lastrowid
                cursor.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", (aid, data, peso))
                msg = f"Animal {brinco} cadastrado."
        except Exception as e:
            logger.error(f"Erro cadastro: {e}", exc_info=True)
            msg = f"Erro: {e}"
    return render_template("cadastro.html", mensagem=msg)

@operacional_bp.route('/animal/<int:id_animal>')
@login_required
def detalhes(id_animal):
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM animais WHERE id=%s AND user_id=%s", (id_animal, current_user.id))
            animal = cursor.fetchone()
            if not animal: return redirect(url_for('operacional.painel'))
            
            cursor.execute("SELECT * FROM pesagens WHERE animal_id=%s ORDER BY data_pesagem DESC", (id_animal,))
            pesagens = cursor.fetchall()
            cursor.execute("SELECT * FROM medicacoes WHERE animal_id=%s", (id_animal,))
            meds = cursor.fetchall()
            cursor.execute("SELECT peso_final, ganho_total, dias, gmd FROM v_gmd_analitico WHERE animal_id=%s", (id_animal,))
            view = cursor.fetchone()
            
            kpis = {'peso_atual': view[0] if view else (pesagens[0][3] if pesagens else 0), 
                    'ganho_total': view[1] if view else 0, 'dias': view[2] if view else 0, 
                    'gmd': "{:.3f}".format(view[3]) if view else "0.000",
                    'custo_total': f"{(float(animal[4] or 0) + sum(float(m[4] or 0) for m in meds)):.2f}"}
            
            return render_template("detalhes.html", animal=animal, historico_peso=pesagens, historico_med=meds, indicadores=kpis)
    except Exception as e:
        logger.error(f"Erro detalhes: {e}", exc_info=True)
        return redirect(url_for('operacional.painel'))

@operacional_bp.route('/vender/<int:id_animal>', methods=['GET', 'POST'])
@login_required
def vender(id_animal):
    if request.method == 'POST':
        try:
            dt, peso, val = request.form['data_venda'], float(request.form['peso_venda']), float(request.form['valor_arroba'])
            with get_db_cursor() as cursor:
                cursor.execute("SELECT id FROM animais WHERE id=%s AND user_id=%s", (id_animal, current_user.id))
                if cursor.fetchone():
                    cursor.execute("UPDATE animais SET data_venda=%s, preco_venda=%s WHERE id=%s", (dt, (peso/30)*val, id_animal))
                    cursor.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", (id_animal, dt, peso))
            return redirect(url_for('operacional.detalhes', id_animal=id_animal))
        except Exception as e:
            logger.error(f"Erro vender: {e}", exc_info=True)
    return render_template('vender.html', id_animal=id_animal)

@operacional_bp.route('/medicar/<int:id_animal>', methods=['GET', 'POST'])
@login_required
def medicar(id_animal):
    if request.method == 'POST':
        try:
            with get_db_cursor() as cursor:
                cursor.execute("SELECT id FROM animais WHERE id=%s AND user_id=%s", (id_animal, current_user.id))
                if cursor.fetchone():
                    cursor.execute("INSERT INTO medicacoes (animal_id, data_aplicacao, nome_medicamento, custo, observacoes) VALUES (%s, %s, %s, %s, %s)", 
                                   (id_animal, request.form['data_aplicacao'], request.form['nome'], request.form['custo'], request.form['obs']))
            return redirect(url_for('operacional.detalhes', id_animal=id_animal))
        except Exception as e:
            logger.error(f"Erro medicar: {e}", exc_info=True)
    return render_template('medicar.html', id_animal=id_animal)

@operacional_bp.route('/pesar/<int:id_animal>', methods=['GET', 'POST'])
@login_required
def nova_pesagem(id_animal):
    if request.method == 'POST':
        try:
            with get_db_cursor() as cursor:
                cursor.execute("SELECT id FROM animais WHERE id=%s AND user_id=%s", (id_animal, current_user.id))
                if cursor.fetchone():
                    cursor.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", 
                                   (id_animal, request.form['data_pesagem'], request.form['peso']))
            return redirect(url_for('operacional.detalhes', id_animal=id_animal))
        except Exception as e:
            logger.error(f"Erro pesar: {e}", exc_info=True)
    return render_template('nova_pesagem.html', id_animal=id_animal)

@operacional_bp.route('/excluir_animal/<int:id_animal>')
@login_required
def excluir_animal(id_animal):
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id FROM animais WHERE id=%s AND user_id=%s", (id_animal, current_user.id))
            if cursor.fetchone():
                cursor.execute("DELETE FROM pesagens WHERE animal_id=%s", (id_animal,))
                cursor.execute("DELETE FROM medicacoes WHERE animal_id=%s", (id_animal,))
                cursor.execute("DELETE FROM animais WHERE id=%s", (id_animal,))
    except Exception as e:
        logger.error(f"Erro excluir: {e}", exc_info=True)
    return redirect(url_for('operacional.painel'))

@operacional_bp.route('/excluir_pesagem/<int:id_pesagem>')
@login_required
def excluir_pesagem(id_pesagem):
    aid = None
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT p.animal_id FROM pesagens p JOIN animais a ON p.animal_id=a.id WHERE p.id=%s AND a.user_id=%s", (id_pesagem, current_user.id))
            res = cursor.fetchone()
            if res:
                aid = res[0]
                cursor.execute("DELETE FROM pesagens WHERE id=%s", (id_pesagem,))
    except Exception as e:
        logger.error(f"Erro excluir pesagem: {e}", exc_info=True)
    if aid: return redirect(url_for('operacional.detalhes', id_animal=aid))
    return redirect(url_for('operacional.painel'))