from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from db_config import get_db_cursor
import math
import logging
from datetime import datetime

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
            # ADICIONAMOS 'deleted_at IS NULL' COMO REGRA PADRÃO
            conds, params = ["user_id = %s", "deleted_at IS NULL"], [current_user.id] # <--- MUDANÇA AQUI
            
            if termo: 
                conds.append("brinco LIKE %s")
                params.append(f"{termo}%")
            
            if status == 'ativos': 
                conds.append("data_venda IS NULL")
            elif status == 'vendidos': 
                conds.append("data_venda IS NOT NULL")
            
            where = " WHERE " + " AND ".join(conds)
            
            # O resto continua igual...
            cursor.execute(f"SELECT COUNT(*) FROM animais {where}", tuple(params))
            total = cursor.fetchone()[0]
            
            cursor.execute(f"SELECT id, brinco, sexo, data_compra, preco_compra, data_venda, preco_venda FROM animais {where} ORDER BY LENGTH(brinco) ASC, brinco ASC LIMIT %s OFFSET %s", tuple(params + [limit, offset]))
            animais = cursor.fetchall()
            if total > 0: total_pg = math.ceil(total / limit)
    except Exception as e:
        logger.error(f"Erro painel: {e}", exc_info=True)
    
    return render_template("index.html", lista_animais=animais, pagina_atual=pg, total_paginas=total_pg, busca=termo, status=status)

@operacional_bp.route('/lixeira')
@login_required
def lixeira():
    animais = []
    termo = request.args.get('busca', '')
    pg = request.args.get('page', 1, type=int)
    limit, offset = 20, (pg - 1) * 20
    total_pg = 1

    try:
        with get_db_cursor() as cursor:
            # FILTRO FIXO: Traz apenas o que tem data de exclusão (deleted_at IS NOT NULL)
            conds, params = ["user_id = %s", "deleted_at IS NOT NULL"], [current_user.id]
            
            if termo:
                conds.append("brinco LIKE %s")
                params.append(f"{termo}%")
            
            where = " WHERE " + " AND ".join(conds)
            
            # Paginação
            cursor.execute(f"SELECT COUNT(*) FROM animais {where}", tuple(params))
            total = cursor.fetchone()[0]
            
            # Busca os dados (Note que trazemos deleted_at para mostrar na tela)
            cursor.execute(f"""
                SELECT id, brinco, sexo, deleted_at 
                FROM animais {where} 
                ORDER BY deleted_at DESC 
                LIMIT %s OFFSET %s
            """, tuple(params + [limit, offset]))
            
            animais = cursor.fetchall()
            if total > 0: total_pg = math.ceil(total / limit)
            
    except Exception as e:
        logger.error(f"Erro lixeira: {e}", exc_info=True)
    
    return render_template("lixeira.html", lista_animais=animais, pagina_atual=pg, total_paginas=total_pg, busca=termo)

# 2. ATUALIZE A ROTA DE RESTAURAR (Para voltar para a lixeira)
@operacional_bp.route('/restaurar_animal/<int:id_animal>')
@login_required
def restaurar_animal(id_animal):
    try:
        with get_db_cursor() as cursor:
            # Remove a data de exclusão (NULL), trazendo o animal de volta à vida
            cursor.execute("UPDATE animais SET deleted_at = NULL WHERE id=%s AND user_id=%s", (id_animal, current_user.id))
    except Exception as e:
        logger.error(f"Erro restaurar: {e}", exc_info=True)
    
    # Redireciona para a lixeira para o usuário ver que o item sumiu de lá (foi restaurado)
    return redirect(url_for('operacional.lixeira'))

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
            # Verifica se o animal é do usuário antes de "apagar"
            cursor.execute("SELECT id FROM animais WHERE id=%s AND user_id=%s", (id_animal, current_user.id))
            if cursor.fetchone():
                # SOFT DELETE: Marcamos a data e hora atual
                now = datetime.now()
                cursor.execute("UPDATE animais SET deleted_at=%s WHERE id=%s", (now, id_animal))
                
    except Exception as e:
        logger.error(f"Erro excluir: {e}", exc_info=True)
    return redirect(url_for('operacional.painel'))

@operacional_bp.route('/excluir_pesagem/<int:id_pesagem>')
@login_required
def excluir_pesagem(id_pesagem):
    aid = None
    try:
        with get_db_cursor() as cursor:
            # Busca o animal_id para poder redirecionar de volta para a ficha certa
            cursor.execute("SELECT p.animal_id FROM pesagens p JOIN animais a ON p.animal_id=a.id WHERE p.id=%s AND a.user_id=%s", (id_pesagem, current_user.id))
            res = cursor.fetchone()
            if res:
                aid = res[0]
                # SOFT DELETE NA PESAGEM
                cursor.execute("UPDATE pesagens SET deleted_at=%s WHERE id=%s", (datetime.now(), id_pesagem))
    except Exception as e:
        logger.error(f"Erro excluir pesagem: {e}", exc_info=True)
        
    if aid: return redirect(url_for('operacional.detalhes', id_animal=aid))
    return redirect(url_for('operacional.painel'))

@operacional_bp.route('/vacinacao-coletiva', methods=['GET', 'POST'])
@login_required
def vacinacao_coletiva():
    # 1. PROCESSAMENTO DO FORMULÁRIO (SALVAR)
    if request.method == 'POST':
        try:
            # Pega os dados comuns a todos
            dt = request.form['data_aplicacao']
            nome = request.form['nome']
            custo = request.form['custo']
            obs = request.form['obs']
            
            # Pega a LISTA de animais selecionados (Checkboxes)
            animais_ids = request.form.getlist('animais_ids') 

            if not animais_ids:
                return render_template('vacinacao_lote.html', erro="Nenhum animal selecionado!", animais=[])

            with get_db_cursor() as cursor:
                # Loop para inserir um registro para cada animal marcado
                sql = """
                    INSERT INTO medicacoes (animal_id, data_aplicacao, nome_medicamento, custo, observacoes) 
                    VALUES (%s, %s, %s, %s, %s)
                """
                for animal_id in animais_ids:
                    cursor.execute(sql, (animal_id, dt, nome, custo, obs))
            
            # Sucesso: volta para o painel
            return redirect(url_for('operacional.painel'))

        except Exception as e:
            logger.error(f"Erro vacinacao lote: {e}", exc_info=True)
            return "Erro ao processar vacinação."

    # 2. EXIBIÇÃO DA TELA (CARREGAR LISTA)
    try:
        with get_db_cursor() as cursor:
            # Busca apenas animais ATIVOS (que estão no pasto)
            cursor.execute("""
                SELECT id, brinco 
                FROM animais 
                WHERE user_id = %s AND data_venda IS NULL 
                ORDER BY brinco ASC
            """, (current_user.id,))
            lista_animais = cursor.fetchall()
            
        return render_template('vacinacao_lote.html', animais=lista_animais)
    
    except Exception as e:
        logger.error(f"Erro carregar lote: {e}", exc_info=True)
        return redirect(url_for('operacional.painel'))