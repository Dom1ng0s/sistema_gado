import os
import logging
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from db_config import get_db_connection, close_db_connection
from contextlib import contextmanager
from datetime import date, datetime, timedelta
import math

# ======================================================================
# 0. CONFIGURAÇÃO DE LOGS (PROFISSIONALISMO)
# ======================================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ======================================================================
# 1. INICIALIZAÇÃO DO APP E CONFIGURAÇÃO DE SEGURANÇA
# ======================================================================
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'chave_desenvolvimento_segura_123')

# ======================================================================
# 2. CONFIGURAÇÃO DO FLASK-LOGIN
# ======================================================================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ======================================================================
# 3. MODELO DE USUÁRIO E USER LOADER
# ======================================================================
class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

    @staticmethod
    def get_user_id(user_id):
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT id, username, password_hash FROM usuarios WHERE id = %s", (user_id,))
                dados = cursor.fetchone()
                cursor.close()
                if dados:
                    return User(dados[0], dados[1], dados[2])
            finally:
                close_db_connection(conn)
        return None

@login_manager.user_loader
def load_user(user_id):
    return User.get_user_id(user_id)

# ======================================================================
# 4. CONTEXT MANAGER PARA CONEXÃO COM O BANCO DE DADOS
# ======================================================================
@contextmanager
def get_db_cursor():
    conn = get_db_connection()
    if conn is None:
        raise ConnectionError("Não foi possível estabelecer conexão com o banco de dados.")
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit() 
    except Exception as e:
        conn.rollback() 
        raise e
    finally:
        close_db_connection(conn)

# ======================================================================
# 5. ROTAS DE AUTENTICAÇÃO E NAVEGAÇÃO BÁSICA
# ======================================================================

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect('/painel')
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect('/painel')

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
                        return redirect('/painel')
        except ConnectionError:
            return render_template('login.html', mensagem="Erro de conexão com o banco de dados.")
        except Exception as e:
            logger.error(f"Erro no login: {e}", exc_info=True)
        
        return render_template('login.html', mensagem="Usuário ou senha incorretos")
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')

@app.route('/novo_usuario', methods=['GET', 'POST'])
def novo_usuario():
    mensagem = None
    if request.method == 'POST':
        novo_user = request.form['username'].strip()
        nova_senha = request.form['password'].strip()
        
        if not novo_user or not nova_senha:
             return render_template('novo_usuario.html', mensagem="Preencha todos os campos.")

        try:
            with get_db_cursor() as cursor:
                cursor.execute("SELECT id FROM usuarios WHERE username = %s", (novo_user,))
                if cursor.fetchone():
                    mensagem = f"Erro: Usuário '{novo_user}' já existe."
                else:
                    hash_senha = generate_password_hash(nova_senha)
                    cursor.execute("INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)", (novo_user, hash_senha))
                    mensagem = f"Sucesso! Usuário '{novo_user}' criado."
        except ConnectionError:
            mensagem = "Erro de conexão com o banco de dados."
        except Exception as e:
            mensagem = f"Erro: {e}"
            logger.error(f"Erro ao criar usuário: {e}", exc_info=True)
            
    return render_template('novo_usuario.html', mensagem=mensagem)

# ======================================================================
# 6. ROTAS PRINCIPAIS DA APLICAÇÃO
# ======================================================================

@app.route('/painel')
@login_required
def painel():
    animais = []
    termo_busca = request.args.get('busca', '')
    filtro_status = request.args.get('status', 'todos') 
    
    pagina_atual = request.args.get('page', 1, type=int)
    itens_por_pagina = 20
    offset = (pagina_atual - 1) * itens_por_pagina
    
    total_animais = 0
    total_paginas = 1

    try:
        with get_db_cursor() as cursor:
            colunas = "id, brinco, sexo, data_compra, preco_compra, data_venda, preco_venda"
            condicoes = ["user_id = %s"]
            parametros = [current_user.id]

            if termo_busca:
                condicoes.append("brinco LIKE %s")
                parametros.append(f"{termo_busca}%")

            if filtro_status == 'ativos':
                condicoes.append("data_venda IS NULL")
            elif filtro_status == 'vendidos':
                condicoes.append("data_venda IS NOT NULL")
            
            where_clause = " WHERE " + " AND ".join(condicoes)

            sql_count = f"SELECT COUNT(*) FROM animais {where_clause}"
            cursor.execute(sql_count, tuple(parametros))
            total_animais = cursor.fetchone()[0]

            sql_data = f"SELECT {colunas} FROM animais {where_clause} ORDER BY LENGTH(brinco) ASC, brinco ASC LIMIT %s OFFSET %s"
            params_data = parametros + [itens_por_pagina, offset] 
            
            cursor.execute(sql_data, tuple(params_data))
            animais = cursor.fetchall()
            
            if total_animais > 0:
                total_paginas = math.ceil(total_animais / itens_por_pagina)
            
    except ConnectionError:
        pass 
    except Exception as e:
        logger.error(f"Erro no painel: {e}", exc_info=True)
    
    return render_template("index.html", 
                           lista_animais=animais, 
                           pagina_atual=pagina_atual, 
                           total_paginas=total_paginas,
                           busca=termo_busca,
                           status=filtro_status)

def calcular_kpis_unificados(cursor, user_id):
    dados = {
        'qtd_animais': 0, 'gmd_medio': 0.0, 'custo_mensal_total': 0.0,
        'custo_diaria': 0.0, 'custo_arroba': 0.0, 'dias_para_arroba': 0,
        'arrendamento': 0.0, 'suplementacao': 0.0, 'mao_obra': 0.0, 'extras': 0.0
    }

    cursor.execute("SELECT COUNT(*) FROM animais WHERE user_id = %s AND data_venda IS NULL", (user_id,))
    dados['qtd_animais'] = cursor.fetchone()[0]

    cursor.execute("""
        SELECT AVG(v.gmd) FROM v_gmd_analitico v 
        JOIN animais a ON v.animal_id = a.id 
        WHERE v.user_id = %s AND a.data_venda IS NULL
    """, (user_id,))
    res_gmd = cursor.fetchone()
    if res_gmd and res_gmd[0]:
        dados['gmd_medio'] = float(res_gmd[0])

    data_limite = date.today() - timedelta(days=90)
    cursor.execute("""
        SELECT tipo_custo, SUM(valor) 
        FROM custos_operacionais 
        WHERE user_id = %s AND data_custo >= %s
        GROUP BY tipo_custo
    """, (user_id, data_limite))
    
    total_trimestre = 0.0
    for tipo, valor_total in cursor.fetchall():
        media_mensal = float(valor_total) / 3
        total_trimestre += media_mensal
        if tipo == 'Arrendamento': dados['arrendamento'] += media_mensal
        elif tipo == 'Nutrição': dados['suplementacao'] += media_mensal
        elif tipo == 'Salário': dados['mao_obra'] += media_mensal
        else: dados['extras'] += media_mensal

    dados['custo_mensal_total'] = total_trimestre

    if dados['qtd_animais'] > 0:
        dados['custo_diaria'] = (dados['custo_mensal_total'] / dados['qtd_animais']) / 30
    
    if dados['gmd_medio'] > 0:
        dados['dias_para_arroba'] = 30 / dados['gmd_medio']
        dados['custo_arroba'] = dados['custo_diaria'] * dados['dias_para_arroba']

    return dados

@app.route('/financeiro')
@login_required
def financeiro():
    ano_atual = date.today().year
    ano_selecionado = request.args.get('ano', default=ano_atual, type=int)
    
    view_data = {
        'valor_rebanho': 0, 'saldo_total_operacao': 0, 'classe_saldo': 'bg-verde',
        'entradas_ano': 0, 'saidas_ano': 0, 'reposicao_ano': 0, 
        'custos_op_ano': 0, 'med_ano': 0, 'balanco_ano': 0,
        'custo_diaria': "---", 'custo_arroba': "---"
    }
    
    anos_disponiveis = [ano_atual]
    lista_custos_detalhada = []

    try:
        with get_db_cursor() as cursor:
            uid = current_user.id
            
            cursor.execute("SELECT SUM(preco_compra) FROM animais WHERE data_venda IS NULL AND user_id = %s", (uid,))
            res_rebanho = cursor.fetchone()
            if res_rebanho and res_rebanho[0]:
                view_data['valor_rebanho'] = f"{res_rebanho[0]:,.2f}"

            cursor.execute("SELECT ano, total_entradas, total_compras, total_med, total_ops FROM v_fluxo_caixa WHERE user_id = %s ORDER BY ano DESC", (uid,))
            historico = cursor.fetchall()
            
            if historico:
                anos_disponiveis = [row[0] for row in historico]
                total_receita = sum(row[1] for row in historico)
                total_despesa = sum(row[2] + row[3] + row[4] for row in historico)
                saldo = total_receita - total_despesa
                view_data['saldo_total_operacao'] = f"{saldo:,.2f}"
                view_data['classe_saldo'] = 'bg-verde' if saldo >= 0 else 'bg-vermelho'
                
                dados_ano = next((row for row in historico if row[0] == ano_selecionado), None)
                if dados_ano:
                    _, ent, comp, med, ops = dados_ano
                    view_data['entradas_ano'] = f"{ent:,.2f}"
                    view_data['reposicao_ano'] = f"{comp:,.2f}"
                    view_data['med_ano'] = f"{med:,.2f}"
                    view_data['custos_op_ano'] = f"{ops:,.2f}"
                    view_data['saidas_ano'] = f"{(comp + med + ops):,.2f}"
                    view_data['balanco_ano'] = f"{(ent - (comp + med + ops)):,.2f}"

            kpis = calcular_kpis_unificados(cursor, uid)
            if kpis['custo_arroba'] > 0:
                view_data['custo_diaria'] = f"{kpis['custo_diaria']:.2f}"
                view_data['custo_arroba'] = f"{kpis['custo_arroba']:.2f}"

            cursor.execute("""
                SELECT data_custo, categoria, tipo_custo, valor, descricao 
                FROM custos_operacionais 
                WHERE user_id = %s AND YEAR(data_custo) = %s 
                ORDER BY data_custo DESC
            """, (uid, ano_selecionado))
            lista_custos_detalhada = cursor.fetchall()

    except Exception as e:
        logger.error(f"Erro financeiro: {e}", exc_info=True)

    return render_template('financeiro.html', financeiro=view_data, ano_selecionado=ano_selecionado, anos=anos_disponiveis, detalhes_custos=lista_custos_detalhada)

@app.route('/simulador-custo', methods=['GET', 'POST'])
@login_required
def simulador_custo():
    resultados = None
    sugestoes = {'qtd_animais': 0, 'gmd_medio': 0.0, 'arrendamento': 0.0, 'suplementacao': 0.0, 'mao_obra': 0.0, 'extras': 0.0}
    
    try:
        if request.method == 'GET':
            with get_db_cursor() as cursor:
                kpis = calcular_kpis_unificados(cursor, current_user.id)
                sugestoes = kpis 

    except Exception as e:
        logger.error(f"Erro sugestão simulador: {e}", exc_info=True)

    if request.method == 'POST':
        try:
            qtd = int(request.form.get('qtd_animais', 1))
            gmd = float(request.form.get('gmd', '0').replace(',', '.'))
            c_arrendamento = float(request.form.get('custo_arrendamento', '0').replace(',', '.'))
            c_suple = float(request.form.get('custo_suplementacao', '0').replace(',', '.'))
            c_mao_obra = float(request.form.get('custo_mao_obra', '0').replace(',', '.'))
            c_extras = float(request.form.get('custos_extras', '0').replace(',', '.'))

            sugestoes.update({
                'qtd_animais': qtd, 'gmd_medio': gmd,
                'arrendamento': c_arrendamento, 'suplementacao': c_suple, 
                'mao_obra': c_mao_obra, 'extras': c_extras
            })

            custo_mensal = c_arrendamento + c_suple + c_mao_obra + c_extras
            custo_diaria = 0
            if qtd > 0: custo_diaria = (custo_mensal / qtd) / 30
            
            dias_arroba = 0
            if gmd > 0: dias_arroba = 30 / gmd
            
            custo_arroba = custo_diaria * dias_arroba

            resultados = {
                'custo_mensal_total': f"{custo_mensal:,.2f}",
                'custo_diaria': f"{custo_diaria:,.2f}",
                'dias_arroba': int(dias_arroba),
                'custo_arroba': f"{custo_arroba:,.2f}"
            }

        except ValueError:
            resultados = {'erro': "Erro numérico."}

    return render_template('simulador_custo.html', sugestoes=sugestoes, resultados=resultados)

@app.route('/graficos')
@login_required
def graficos():
    return render_template('graficos.html')

@app.route('/dados-graficos')
@login_required
def dados_graficos_api():
    try:
        with get_db_cursor() as cursor:
            uid = current_user.id
            
            cursor.execute("SELECT sexo, COUNT(*) FROM animais WHERE user_id = %s AND data_venda IS NULL GROUP BY sexo", (uid,))
            dados_sexo = {sexo: qtd for sexo, qtd in cursor.fetchall()}
            
            cursor.execute("""
                SELECT p.peso 
                FROM pesagens p
                INNER JOIN (
                    SELECT animal_id, MAX(id) as max_id FROM pesagens GROUP BY animal_id
                ) ultimas ON p.id = ultimas.max_id
                INNER JOIN animais a ON p.animal_id = a.id
                WHERE a.user_id = %s AND a.data_venda IS NULL
            """, (uid,))
            pesos_brutos = cursor.fetchall()

            cat_peso = {'Menos de 10@': 0, '10@ a 15@': 0, '15@ a 20@': 0, 'Mais de 20@': 0}
            for (peso_kg,) in pesos_brutos:
                peso_arroba = float(peso_kg) / 30
                if peso_arroba < 10: cat_peso['Menos de 10@'] += 1
                elif 10 <= peso_arroba < 15: cat_peso['10@ a 15@'] += 1
                elif 15 <= peso_arroba < 20: cat_peso['15@ a 20@'] += 1
                else: cat_peso['Mais de 20@'] += 1

            cursor.execute("""
                SELECT AVG(v.gmd) 
                FROM v_gmd_analitico v
                JOIN animais a ON v.animal_id = a.id
                WHERE v.user_id = %s AND a.data_venda IS NULL
            """, (uid,))
            
            media_result = cursor.fetchone()[0]
            gmd_medio_val = float(media_result) if media_result else 0.0

            # CORREÇÃO FASE 1: Retorno explícito do Status 200
            return jsonify({
                'sexo': dados_sexo, 
                'peso': cat_peso, 
                'gmd_medio': gmd_medio_val 
            }), 200

    except Exception as e:
        logger.error(f"Erro na API de gráficos: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route("/cadastro", methods=["GET", "POST"])
@login_required
def cadastro():
    mensagem = None
    if request.method == "POST":
        try:
            brinco = request.form["brinco"].strip()
            sexo = request.form["sexo"]
            data = request.form["data_compra"]
            
            try:
                peso = float(request.form["peso_compra"])
                valor_arroba = float(request.form["valor_arroba"])
            except ValueError:
                return render_template("cadastro.html", mensagem="Erro: Peso e Valor devem ser números.")

            if peso <= 0 or valor_arroba <= 0:
                return render_template("cadastro.html", mensagem="Erro: Valores devem ser positivos.")
            if not brinco:
                return render_template("cadastro.html", mensagem="Erro: Brinco obrigatório.")

            preco_calc = (peso / 30) * valor_arroba

            with get_db_cursor() as cursor:
                cursor.execute("SELECT id FROM animais WHERE brinco = %s AND user_id = %s", (brinco, current_user.id))
                if cursor.fetchone():
                     return render_template("cadastro.html", mensagem=f"Erro: O brinco {brinco} já existe no seu rebanho.")

                sql = "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id) VALUES (%s, %s, %s, %s, %s)"
                val = (brinco, sexo, data, preco_calc, current_user.id)
                cursor.execute(sql, val)
                id_animal = cursor.lastrowid
                
                cursor.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", (id_animal, data, peso))
                
                mensagem = f"Sucesso! Animal {brinco} cadastrado."
                
        except ConnectionError:
            mensagem = "Erro de conexão com o banco de dados."
        except Exception as e:
            mensagem = f"Erro Inesperado: {e}"
            logger.error(f"Erro no cadastro: {e}", exc_info=True)
    
    return render_template("cadastro.html", mensagem=mensagem)

@app.route('/custos_operacionais', methods=['GET', 'POST'])
@login_required
def custos_operacionais():
    mensagem = None
    if request.method == 'POST':
        try:
            categoria = request.form.get('categoria')
            if categoria == 'Fixo':
                tipo = request.form.get('tipo_fixo')
            else:
                tipo = request.form.get('tipo_variavel')
            
            valor = float(request.form.get('valor'))
            data = request.form.get('data')
            desc = request.form.get('descricao')

            with get_db_cursor() as cursor:
                sql = "INSERT INTO custos_operacionais (user_id, categoria, tipo_custo, valor, data_custo, descricao) VALUES (%s, %s, %s, %s, %s, %s)"
                cursor.execute(sql, (current_user.id, categoria, tipo, valor, data, desc))
                mensagem = "Custo registrado com sucesso!"

        except Exception as e:
            mensagem = f"Erro ao salvar: {e}"
            logger.error(f"Erro em custos: {e}", exc_info=True)

    return render_template('custos_operacionais.html', mensagem=mensagem)

@app.route('/animal/<int:id_animal>')
@login_required
def detalhes(id_animal):
    animal, pesagens, medicacoes = None, [], []
    kpis = {'peso_atual': 0, 'ganho_total': 0, 'gmd': "0.000", 'dias': 0, 'custo_total': "0.00"}

    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM animais WHERE id = %s AND user_id = %s", (id_animal, current_user.id))
            animal = cursor.fetchone()
            
            if animal:
                cursor.execute("SELECT * FROM pesagens WHERE animal_id = %s ORDER BY data_pesagem DESC", (id_animal,))
                pesagens = cursor.fetchall()
                
                cursor.execute("SELECT * FROM medicacoes WHERE animal_id = %s", (id_animal,))
                medicacoes = cursor.fetchall()
                
                cursor.execute("""
                    SELECT peso_final, ganho_total, dias, gmd 
                    FROM v_gmd_analitico 
                    WHERE animal_id = %s
                """, (id_animal,))
                
                dados_view = cursor.fetchone()
                
                if dados_view:
                    kpis['peso_atual'] = dados_view[0]
                    kpis['ganho_total'] = dados_view[1]
                    kpis['dias'] = dados_view[2]
                    kpis['gmd'] = "{:.3f}".format(dados_view[3]) 
                elif pesagens:
                    kpis['peso_atual'] = pesagens[0][3]

    except Exception as e:
        logger.error(f"Erro nos detalhes: {e}", exc_info=True)

    if not animal:
        return redirect('/painel')

    custo_compra = float(animal[4]) if animal[4] else 0.0
    custo_sanitario = sum(float(m[4]) for m in medicacoes if m[4])
    kpis['custo_total'] = f"{custo_compra + custo_sanitario:.2f}"

    return render_template("detalhes.html", animal=animal, historico_peso=pesagens, historico_med=medicacoes, indicadores=kpis)

@app.route('/vender/<int:id_animal>', methods=['GET', 'POST'])
@login_required
def vender(id_animal):
    if request.method == 'POST':
        try:
            data_venda = request.form['data_venda']
            peso_venda = float(request.form['peso_venda'])
            valor_arroba = float(request.form['valor_arroba'])
            preco_final = (peso_venda / 30) * valor_arroba

            with get_db_cursor() as cursor:
                cursor.execute("SELECT id FROM animais WHERE id = %s AND user_id = %s", (id_animal, current_user.id))
                if not cursor.fetchone():
                    return redirect('/painel') 

                sql = "UPDATE animais SET data_venda = %s, preco_venda = %s WHERE id = %s AND user_id = %s"
                cursor.execute(sql, (data_venda, preco_final, id_animal, current_user.id))
                
                cursor.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", (id_animal, data_venda, peso_venda))
                
            return redirect(f"/animal/{id_animal}")
        
        except ConnectionError:
            logger.error("Erro de conexão ao vender animal.", exc_info=True)
            return redirect(f"/animal/{id_animal}")
        except Exception as e:
            logger.error(f"Erro ao vender animal: {e}", exc_info=True)
            return redirect(f"/animal/{id_animal}")

    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id FROM animais WHERE id = %s AND user_id = %s", (id_animal, current_user.id))
            if not cursor.fetchone():
                return redirect('/painel')
    except:
        return redirect('/painel')

    return render_template('vender.html', id_animal=id_animal)

@app.route('/medicar/<int:id_animal>', methods=['GET', 'POST'])
@login_required
def medicar(id_animal):
    don_exists = False
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id FROM animais WHERE id = %s AND user_id = %s", (id_animal, current_user.id))
            if cursor.fetchone():
                don_exists = True
    except:
        return redirect('/painel')

    if not don_exists:
        return redirect('/painel')

    if request.method == 'POST':
        try:
            with get_db_cursor() as cursor:
                sql = "INSERT INTO medicacoes (animal_id, data_aplicacao, nome_medicamento, custo, observacoes) VALUES (%s, %s, %s, %s, %s)"
                val = (id_animal, request.form['data_aplicacao'], request.form['nome'], request.form['custo'], request.form['obs'])
                cursor.execute(sql, val)
            return redirect(f"/animal/{id_animal}")
        except ConnectionError:
            logger.error("Erro de conexão ao medicar animal.", exc_info=True)
            return redirect(f"/animal/{id_animal}")
        except Exception as e:
            logger.error(f"Erro ao medicar animal: {e}", exc_info=True)
            return redirect(f"/animal/{id_animal}")

    return render_template('medicar.html', id_animal=id_animal)

@app.route('/pesar/<int:id_animal>', methods=['GET', 'POST'])
@login_required
def nova_pesagem(id_animal):
    don_exists = False
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id FROM animais WHERE id = %s AND user_id = %s", (id_animal, current_user.id))
            if cursor.fetchone():
                don_exists = True
    except:
        return redirect('/painel') 

    if not don_exists:
        return redirect('/painel')

    if request.method == 'POST':
        try:
            with get_db_cursor() as cursor:
                cursor.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", (id_animal, request.form['data_pesagem'], request.form['peso']))
            return redirect(f"/animal/{id_animal}")
        except ConnectionError:
            logger.error("Erro de conexão ao pesar animal.", exc_info=True)
            return redirect(f"/animal/{id_animal}")
        except Exception as e:
            logger.error(f"Erro ao pesar animal: {e}", exc_info=True)
            return redirect(f"/animal/{id_animal}")

    return render_template('nova_pesagem.html', id_animal=id_animal)

@app.route('/excluir_animal/<int:id_animal>')
@login_required
def excluir_animal(id_animal):
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id FROM animais WHERE id = %s AND user_id = %s", (id_animal, current_user.id))
            if cursor.fetchone():
                cursor.execute("DELETE FROM pesagens WHERE animal_id = %s", (id_animal,))
                cursor.execute("DELETE FROM medicacoes WHERE animal_id = %s", (id_animal,))
                cursor.execute("DELETE FROM animais WHERE id = %s", (id_animal,))
    except ConnectionError:
        logger.error("Erro de conexão ao excluir animal.", exc_info=True)
    except Exception as e:
        logger.error(f"Erro ao excluir animal: {e}", exc_info=True)
        
    return redirect("/painel")

@app.route('/excluir_pesagem/<int:id_pesagem>')
@login_required
def excluir_pesagem(id_pesagem):
    animal_id = None
    try:
        with get_db_cursor() as cursor:
            sql_check = """
                SELECT p.animal_id FROM pesagens p
                JOIN animais a ON p.animal_id = a.id
                WHERE p.id = %s AND a.user_id = %s
            """
            cursor.execute(sql_check, (id_pesagem, current_user.id))
            result = cursor.fetchone()
            
            if result:
                animal_id = result[0]
                cursor.execute("DELETE FROM pesagens WHERE id = %s", (id_pesagem,))
            
    except ConnectionError:
        logger.error("Erro de conexão ao excluir pesagem.", exc_info=True)
    except Exception as e:
        logger.error(f"Erro ao excluir pesagem: {e}", exc_info=True)
        
    if animal_id:
        return redirect(f"/animal/{animal_id}")
    return redirect("/painel")

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', 'False') == 'True')