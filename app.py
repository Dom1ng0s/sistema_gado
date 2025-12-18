import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from db_config import get_db_connection, close_db_connection
from contextlib import contextmanager
from datetime import date, datetime, timedelta
import math


# ======================================================================
# 1. INICIALIZAÇÃO DO APP E CONFIGURAÇÃO DE SEGURANÇA
# ======================================================================
app = Flask(__name__)

# Chave secreta usada para assinar cookies de sessão.
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
        """Busca um usuário pelo ID no banco de dados."""
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                # Busca o usuário na tabela 'usuarios'
                cursor.execute("SELECT id, username, password_hash FROM usuarios WHERE id = %s", (user_id,))
                dados = cursor.fetchone()
                cursor.close()
                if dados:
                    # Retorna uma instância da classe User
                    return User(dados[0], dados[1], dados[2])
            finally:
                close_db_connection(conn)
        return None

@login_manager.user_loader
def load_user(user_id):
    """Função obrigatória para recarregar o objeto User a partir do ID de sessão."""
    return User.get_user_id(user_id)

# ======================================================================
# 4. CONTEXT MANAGER PARA CONEXÃO COM O BANCO DE DADOS
# Otimização: Garante que a conexão seja aberta e fechada corretamente
# em cada rota, reduzindo a repetição de código.
# ======================================================================
@contextmanager
def get_db_cursor():
    conn = get_db_connection()
    if conn is None:
        raise ConnectionError("Não foi possível estabelecer conexão com o banco de dados.")
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit() # Commit automático para operações de escrita
    except Exception as e:
        conn.rollback() # Rollback em caso de erro
        raise e
    finally:
        close_db_connection(conn)

# ======================================================================
# 5. ROTAS DE AUTENTICAÇÃO E NAVEGAÇÃO BÁSICA
# ======================================================================

@app.route('/')
def index():
    """Redireciona para o painel se logado, ou para o login se deslogado."""
    if current_user.is_authenticated:
        return redirect('/painel')
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Processa o formulário de login e autentica o usuário."""
    if current_user.is_authenticated:
        return redirect('/painel')

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            with get_db_cursor() as cursor:
                # Busca o usuário pelo nome
                cursor.execute("SELECT id, username, password_hash FROM usuarios WHERE username = %s", (username,))
                dados = cursor.fetchone()
                
                if dados:
                    user_obj = User(dados[0], dados[1], dados[2])
                    # Verifica o hash da senha usando werkzeug.security
                    if check_password_hash(user_obj.password_hash, password):
                        login_user(user_obj)
                        return redirect('/painel')
        except ConnectionError:
            return render_template('login.html', mensagem="Erro de conexão com o banco de dados.")
        except Exception as e:
            print(f"Erro no login: {e}")
        
        return render_template('login.html', mensagem="Usuário ou senha incorretos")
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Desloga o usuário e o redireciona para a página de login."""
    logout_user()
    return redirect('/login')

@app.route('/novo_usuario', methods=['GET', 'POST'])
def novo_usuario():
    """Permite a criação de novos usuários (apenas por usuários já logados)."""
    mensagem = None
    if request.method == 'POST':
        novo_user = request.form['username'].strip()
        nova_senha = request.form['password'].strip()
        
        if not novo_user or not nova_senha:
             return render_template('novo_usuario.html', mensagem="Preencha todos os campos.")

        try:
            with get_db_cursor() as cursor:
                # Verifica se o usuário já existe
                cursor.execute("SELECT id FROM usuarios WHERE username = %s", (novo_user,))
                if cursor.fetchone():
                    mensagem = f"Erro: Usuário '{novo_user}' já existe."
                else:
                    # Gera o hash seguro da senha
                    hash_senha = generate_password_hash(nova_senha)
                    cursor.execute("INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)", (novo_user, hash_senha))
                    mensagem = f"Sucesso! Usuário '{novo_user}' criado."
        except ConnectionError:
            mensagem = "Erro de conexão com o banco de dados."
        except Exception as e:
            mensagem = f"Erro: {e}"
            
    return render_template('novo_usuario.html', mensagem=mensagem)

# ======================================================================
# 6. ROTAS PRINCIPAIS DA APLICAÇÃO (PROTEGIDAS E FILTRADAS POR USUÁRIO)
# ======================================================================

@app.route('/painel')
@login_required
def painel():
    animais = []
    termo_busca = request.args.get('busca', '')
    filtro_status = request.args.get('status', 'todos') # Padrão: 'todos'
    
    # Configuração da Paginação
    pagina_atual = request.args.get('page', 1, type=int)
    itens_por_pagina = 20
    offset = (pagina_atual - 1) * itens_por_pagina
    
    total_animais = 0
    total_paginas = 1

    try:
        with get_db_cursor() as cursor:
            colunas = "id, brinco, sexo, data_compra, preco_compra, data_venda, preco_venda"
            
            # --- CONSTRUÇÃO DINÂMICA DA QUERY ---
            condicoes = ["user_id = %s"]
            parametros = [current_user.id]

            # 1. Filtro de Busca (Texto)
            if termo_busca:
                condicoes.append("brinco LIKE %s")
                parametros.append(f"{termo_busca}%") # Busca Otimizada (Prefixo)

            # 2. Filtro de Status (Ativos/Vendidos)
            if filtro_status == 'ativos':
                condicoes.append("data_venda IS NULL")
            elif filtro_status == 'vendidos':
                condicoes.append("data_venda IS NOT NULL")
            
            # Monta a cláusula WHERE
            where_clause = " WHERE " + " AND ".join(condicoes)

            # --- EXECUÇÃO ---
            
            # A. Conta total (para paginação)
            sql_count = f"SELECT COUNT(*) FROM animais {where_clause}"
            cursor.execute(sql_count, tuple(parametros))
            total_animais = cursor.fetchone()[0]

            # B. Busca dados (com limite)
            # Ordena pelo TAMANHO do texto primeiro, depois pelo texto.
# Isso faz '9' (tamanho 1) vir antes de '10' (tamanho 2).
            sql_data = f"SELECT {colunas} FROM animais {where_clause} ORDER BY LENGTH(brinco) ASC, brinco ASC LIMIT %s OFFSET %s"
            # Adiciona params de paginação à lista existente
            params_data = parametros + [itens_por_pagina, offset] 
            
            cursor.execute(sql_data, tuple(params_data))
            animais = cursor.fetchall()
            
            # Calcula total de páginas
            if total_animais > 0:
                total_paginas = math.ceil(total_animais / itens_por_pagina)
            
    except ConnectionError:
        pass # Tratar erro de conexão se necessário
    except Exception as e:
        print(f"Erro no painel: {e}")
    
    return render_template("index.html", 
                           lista_animais=animais, 
                           pagina_atual=pagina_atual, 
                           total_paginas=total_paginas,
                           busca=termo_busca,
                           status=filtro_status) # Passamos o status para o template manter o botão ativo


@app.route('/financeiro')
@login_required
def financeiro():
    """
    Relatório Financeiro + KPIs de Eficiência (Custo @ e Diária)
    """
    ano_atual = date.today().year
    ano_selecionado = request.args.get('ano', default=ano_atual, type=int)
    
    # Estrutura base
    dados = {
        'valor_rebanho': 0, 
        'saldo_total_operacao': 0, 
        'classe_saldo': 'bg-verde',
        'entradas_ano': 0, 
        'saidas_ano': 0, 
        'reposicao_ano': 0, 
        'custos_op_ano': 0, 
        'med_ano': 0,
        'balanco_ano': 0,
        # NOVOS KPIs
        'custo_diaria': "---",
        'custo_arroba': "---"
    }
    
    anos_disponiveis = [ano_atual]
    lista_custos_detalhada = []

    try:
        with get_db_cursor() as cursor:
            uid = current_user.id
            
            # --- PARTE 1: FINANCEIRO CLÁSSICO (Mantido) ---
            cursor.execute("SELECT SUM(preco_compra) FROM animais WHERE data_venda IS NULL AND user_id = %s", (uid,))
            res_rebanho = cursor.fetchone()
            if res_rebanho and res_rebanho[0]:
                dados['valor_rebanho'] = f"{res_rebanho[0]:,.2f}"

            cursor.execute("SELECT ano, total_entradas, total_compras, total_med, total_ops FROM v_fluxo_caixa WHERE user_id = %s ORDER BY ano DESC", (uid,))
            historico = cursor.fetchall()
            
            if historico:
                anos_disponiveis = [row[0] for row in historico]
                total_receita = sum(row[1] for row in historico)
                total_despesa = sum(row[2] + row[3] + row[4] for row in historico)
                saldo_total = total_receita - total_despesa
                dados['saldo_total_operacao'] = f"{saldo_total:,.2f}"
                dados['classe_saldo'] = 'bg-verde' if saldo_total >= 0 else 'bg-vermelho'
                
                dados_ano = next((row for row in historico if row[0] == ano_selecionado), None)
                if dados_ano:
                    _, ent, comp, med, ops = dados_ano
                    dados['entradas_ano'] = f"{ent:,.2f}"
                    dados['reposicao_ano'] = f"{comp:,.2f}"
                    dados['med_ano'] = f"{med:,.2f}"
                    dados['custos_op_ano'] = f"{ops:,.2f}"
                    
                    total_saidas = comp + med + ops
                    dados['saidas_ano'] = f"{total_saidas:,.2f}"
                    dados['balanco_ano'] = f"{(ent - total_saidas):,.2f}"

            # --- PARTE 2: CÁLCULO INTELIGENTE DOS KPIS (Custo @ e Diária) ---
            # Lógica: Usa custos dos últimos 90 dias + GMD Médio Histórico + Qtd Atual
            
            # A. Qtd Animais Atuais
            cursor.execute("SELECT COUNT(*) FROM animais WHERE user_id = %s AND data_venda IS NULL", (uid,))
            qtd_animais = cursor.fetchone()[0]

            # B. GMD Médio
            cursor.execute("""
                SELECT AVG(v.gmd) FROM v_gmd_analitico v 
                JOIN animais a ON v.animal_id = a.id 
                WHERE v.user_id = %s AND a.data_venda IS NULL
            """, (uid,))
            res_gmd = cursor.fetchone()
            gmd_medio = float(res_gmd[0]) if res_gmd and res_gmd[0] else 0.0

            # C. Média Mensal de Custos (Últimos 90 dias)
            data_limite = date.today() - timedelta(days=90)
            cursor.execute("SELECT SUM(valor) FROM custos_operacionais WHERE user_id = %s AND data_custo >= %s", (uid, data_limite))
            res_custos = cursor.fetchone()
            custo_trimestral = float(res_custos[0]) if res_custos and res_custos[0] else 0.0
            custo_mensal_medio = custo_trimestral / 3

            # D. Cálculos Finais
            if qtd_animais > 0 and gmd_medio > 0:
                custo_diaria_val = (custo_mensal_medio / qtd_animais) / 30
                dias_para_arroba = 30 / gmd_medio
                custo_arroba_val = custo_diaria_val * dias_para_arroba
                
                dados['custo_diaria'] = f"{custo_diaria_val:.2f}"
                dados['custo_arroba'] = f"{custo_arroba_val:.2f}"

            # --- PARTE 3: DETALHAMENTO DE CUSTOS (Tabela) ---
            sql_detalhes = """
                SELECT data_custo, categoria, tipo_custo, valor, descricao 
                FROM custos_operacionais 
                WHERE user_id = %s AND YEAR(data_custo) = %s 
                ORDER BY data_custo DESC
            """
            cursor.execute(sql_detalhes, (uid, ano_selecionado))
            lista_custos_detalhada = cursor.fetchall()

    except Exception as e:
        print(f"Erro no financeiro: {e}")

    return render_template('financeiro.html', 
                           financeiro=dados, 
                           ano_selecionado=ano_selecionado, 
                           anos=anos_disponiveis,
                           detalhes_custos=lista_custos_detalhada)

# ======================================================================
# ROTA: SIMULADOR DE CUSTO PRO (Automatizado)
# ======================================================================
@app.route('/simulador-custo', methods=['GET', 'POST'])
@login_required
def simulador_custo():
    resultados = None
    
    # Valores Iniciais (Sugestões Automáticas)
    sugestoes = {
        'qtd_animais': 0, 
        'gmd_medio': 0.0,
        'arrendamento': 0.0, 
        'suplementacao': 0.0,
        'mao_obra': 0.0, 
        'extras': 0.0
    }

    try:
        with get_db_cursor() as cursor:
            uid = current_user.id
            
            # 1. QTD ANIMAIS (Ativos Hoje)
            cursor.execute("SELECT COUNT(*) FROM animais WHERE user_id = %s AND data_venda IS NULL", (uid,))
            res_qtd = cursor.fetchone()
            if res_qtd:
                sugestoes['qtd_animais'] = res_qtd[0]

            # 2. GMD (Média Histórica da View)
            cursor.execute("""
                SELECT AVG(v.gmd) FROM v_gmd_analitico v 
                JOIN animais a ON v.animal_id = a.id 
                WHERE v.user_id = %s AND a.data_venda IS NULL
            """, (uid,))
            gmd_db = cursor.fetchone()[0]
            if gmd_db: 
                sugestoes['gmd_medio'] = float(gmd_db)

            # 3. CUSTOS OPERACIONAIS (Média dos últimos 90 dias / 3 meses)
            # Esta lógica suaviza picos e preenche a planilha automaticamente
            data_limite = date.today() - timedelta(days=90)
            
            sql_custos = """
                SELECT tipo_custo, SUM(valor) 
                FROM custos_operacionais 
                WHERE user_id = %s AND data_custo >= %s
                GROUP BY tipo_custo
            """
            cursor.execute(sql_custos, (uid, data_limite))
            
            for tipo, valor_total in cursor.fetchall():
                media_mensal = float(valor_total) / 3  # Média trimestral
                
                # Mapeamento: Banco de Dados -> Simulador
                if tipo == 'Arrendamento':
                    sugestoes['arrendamento'] += media_mensal
                elif tipo == 'Nutrição':
                    sugestoes['suplementacao'] += media_mensal
                elif tipo == 'Salário':
                    sugestoes['mao_obra'] += media_mensal
                else:
                    # 'Outro', 'Manutenção', 'Energia' vão para Extras
                    sugestoes['extras'] += media_mensal

    except Exception as e:
        print(f"Erro na automação do simulador: {e}")

    # Processamento do Formulário (POST)
    if request.method == 'POST':
        try:
            # Captura valores (o utilizador pode ter editado a sugestão)
            qtd = int(request.form.get('qtd_animais', 1))
            gmd = float(request.form.get('gmd', '0').replace(',', '.'))
            
            c_arrendamento = float(request.form.get('custo_arrendamento', '0').replace(',', '.'))
            c_suple = float(request.form.get('custo_suplementacao', '0').replace(',', '.'))
            c_mao_obra = float(request.form.get('custo_mao_obra', '0').replace(',', '.'))
            c_extras = float(request.form.get('custos_extras', '0').replace(',', '.'))

            # Atualiza sugestões para manter o que foi digitado
            sugestoes.update({
                'qtd_animais': qtd, 'gmd_medio': gmd,
                'arrendamento': c_arrendamento, 'suplementacao': c_suple,
                'mao_obra': c_mao_obra, 'extras': c_extras
            })

            # --- CÁLCULOS MATEMÁTICOS ---
            custo_mensal_total = c_arrendamento + c_suple + c_mao_obra + c_extras
            
            custo_diaria = 0
            if qtd > 0:
                # Custo mensal por cabeça / 30 dias
                custo_diaria = (custo_mensal_total / qtd) / 30
            
            dias_para_arroba = 0
            # Padrão de Mercado: 1@ = 30kg Peso Vivo
            if gmd > 0:
                dias_para_arroba = 30 / gmd
            
            custo_por_arroba = custo_diaria * dias_para_arroba

            resultados = {
                'custo_mensal_total': f"{custo_mensal_total:,.2f}",
                'custo_diaria': f"{custo_diaria:,.2f}",
                'dias_arroba': int(dias_para_arroba),
                'custo_arroba': f"{custo_por_arroba:,.2f}"
            }

        except ValueError:
            resultados = {'erro': "Erro de formato numérico."}

    return render_template('simulador_custo.html', sugestoes=sugestoes, resultados=resultados)


# ======================================================================
# ROTA 1: ENTREGAR A PÁGINA (Visual)
# ======================================================================
@app.route('/graficos')
@login_required
def graficos():
    """Apenas carrega o arquivo HTML. O JavaScript da página buscará os dados depois."""
    return render_template('graficos.html')


# ======================================================================
# ROTA 2: ENTREGAR OS DADOS (API / JSON)
# ======================================================================
@app.route('/dados-graficos')
@login_required
def dados_graficos_api():
    """API de métricas: Sexo, Peso e GMD Médio (KPI)."""
    try:
        with get_db_cursor() as cursor:
            uid = current_user.id
            
            # 1. Sexo
            cursor.execute("SELECT sexo, COUNT(*) FROM animais WHERE user_id = %s AND data_venda IS NULL GROUP BY sexo", (uid,))
            dados_sexo = {sexo: qtd for sexo, qtd in cursor.fetchall()}
            
            # 2. Peso
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

            # 3. GMD MÉDIO (Cálculo Direto no Banco)
            # A view v_gmd_analitico já tem o GMD calculado por animal. 
            # Fazemos a média apenas dos ativos.
            cursor.execute("""
                SELECT AVG(v.gmd) 
                FROM v_gmd_analitico v
                JOIN animais a ON v.animal_id = a.id
                WHERE v.user_id = %s AND a.data_venda IS NULL
            """, (uid,))
            
            media_result = cursor.fetchone()[0]
            gmd_medio_val = float(media_result) if media_result else 0.0

            return jsonify({
                'sexo': dados_sexo, 
                'peso': cat_peso, 
                'gmd_medio': gmd_medio_val # Retorna número único
            })

    except Exception as e:
        print(f"Erro na API de gráficos: {e}")
        return jsonify({'error': str(e)}), 500

@app.route("/cadastro", methods=["GET", "POST"])
@login_required
def cadastro():
    """Permite o cadastro de um novo animal, vinculando-o ao usuário logado."""
    mensagem = None
    if request.method == "POST":
        try:
            # Validação e Limpeza
            brinco = request.form["brinco"].strip()
            sexo = request.form["sexo"]
            data = request.form["data_compra"]
            
            try:
                peso = float(request.form["peso_compra"])
                valor_arroba = float(request.form["valor_arroba"])
            except ValueError:
                return render_template("cadastro.html", mensagem="Erro: Peso e Valor devem ser números.")

            # Validações de negócio
            if peso <= 0 or valor_arroba <= 0:
                return render_template("cadastro.html", mensagem="Erro: Valores devem ser positivos.")
            if not brinco:
                return render_template("cadastro.html", mensagem="Erro: Brinco obrigatório.")

            preco_calc = (peso / 30) * valor_arroba

            with get_db_cursor() as cursor:
                # Verifica se brinco já existe PARA ESTE USUÁRIO (Multi-Tenant Check)
                cursor.execute("SELECT id FROM animais WHERE brinco = %s AND user_id = %s", (brinco, current_user.id))
                if cursor.fetchone():
                     return render_template("cadastro.html", mensagem=f"Erro: O brinco {brinco} já existe no seu rebanho.")

                # Insere o animal, vinculando-o ao usuário logado (current_user.id)
                sql = "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id) VALUES (%s, %s, %s, %s, %s)"
                val = (brinco, sexo, data, preco_calc, current_user.id)
                cursor.execute(sql, val)
                id_animal = cursor.lastrowid
                
                # Registra peso inicial
                cursor.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", (id_animal, data, peso))
                
                mensagem = f"Sucesso! Animal {brinco} cadastrado."
                
        except ConnectionError:
            mensagem = "Erro de conexão com o banco de dados."
        except Exception as e:
            mensagem = f"Erro Inesperado: {e}"
    
    return render_template("cadastro.html", mensagem=mensagem)

@app.route('/custos_operacionais', methods=['GET', 'POST'])
@login_required
def custos_operacionais():
    mensagem = None
    
    if request.method == 'POST':
        try:
            # 1. Captura a categoria (Fixo ou Variável)
            categoria = request.form.get('categoria')
            
            # 2. Decide qual campo de "tipo" ler baseado na categoria
            if categoria == 'Fixo':
                tipo = request.form.get('tipo_fixo') # Vem do Dropdown
            else:
                tipo = request.form.get('tipo_variavel') # Vem do campo de texto manual
            
            valor = float(request.form.get('valor'))
            data = request.form.get('data')
            desc = request.form.get('descricao')

            # 3. Salva no banco (incluindo a categoria)
            with get_db_cursor() as cursor:
                sql = "INSERT INTO custos_operacionais (user_id, categoria, tipo_custo, valor, data_custo, descricao) VALUES (%s, %s, %s, %s, %s, %s)"
                cursor.execute(sql, (current_user.id, categoria, tipo, valor, data, desc))
                mensagem = "Custo registrado com sucesso!"

        except Exception as e:
            mensagem = f"Erro ao salvar: {e}"

    # Para o GET: Buscar custos para exibir na tabela abaixo do formulário
    

    return render_template('custos_operacionais.html', mensagem=mensagem)

@app.route('/animal/<int:id_animal>')
@login_required
def detalhes(id_animal):
    """
    Exibe os detalhes consumindo a VIEW INTELIGENTE do banco (v_gmd_analitico).
    """
    animal, pesagens, medicacoes = None, [], []
    # KPIs padrão caso o animal não tenha dados suficientes na View (ex: só 1 pesagem)
    kpis = {
        'peso_atual': 0, 
        'ganho_total': 0, 
        'gmd': "0.000", 
        'dias': 0, 
        'custo_total': "0.00"
    }

    try:
        with get_db_cursor() as cursor:
            
            # 1. Validação de Segurança (Dono do Animal)
            cursor.execute("SELECT * FROM animais WHERE id = %s AND user_id = %s", (id_animal, current_user.id))
            animal = cursor.fetchone()
            
            if animal:
                # 2. Históricos (Mantidos para as tabelas visuais)
                cursor.execute("SELECT * FROM pesagens WHERE animal_id = %s ORDER BY data_pesagem DESC", (id_animal,))
                pesagens = cursor.fetchall()
                
                cursor.execute("SELECT * FROM medicacoes WHERE animal_id = %s", (id_animal,))
                medicacoes = cursor.fetchall()
                
                # 3. USO DA VIEW (Inteligência do Banco)
                # A view só retorna dados se houver pelo menos 2 pesagens (diferença de tempo)
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
                    kpis['gmd'] = "{:.3f}".format(dados_view[3]) # Formata GMD com 3 casas
                elif pesagens:
                    # Fallback: Se tiver apenas 1 pesagem, o peso atual é a única pesagem
                    kpis['peso_atual'] = pesagens[0][3]

    except Exception as e:
        print(f"Erro nos detalhes: {e}")

    if not animal:
        return redirect('/painel')

    # Cálculo de Custos (Mantido no Python pois soma tabelas distintas)
    custo_compra = float(animal[4]) if animal[4] else 0.0
    custo_sanitario = sum(float(m[4]) for m in medicacoes if m[4])
    kpis['custo_total'] = f"{custo_compra + custo_sanitario:.2f}"

    return render_template("detalhes.html", animal=animal, historico_peso=pesagens, historico_med=medicacoes, indicadores=kpis)
@app.route('/vender/<int:id_animal>', methods=['GET', 'POST'])
@login_required
def vender(id_animal):
    """Processa a venda de um animal, atualizando o registro e registrando o peso final."""
    
    if request.method == 'POST':
        try:
            data_venda = request.form['data_venda']
            peso_venda = float(request.form['peso_venda'])
            valor_arroba = float(request.form['valor_arroba'])
            preco_final = (peso_venda / 30) * valor_arroba

            with get_db_cursor() as cursor:
                # 1. Verifica se o animal pertence ao usuário logado (segurança)
                cursor.execute("SELECT id FROM animais WHERE id = %s AND user_id = %s", (id_animal, current_user.id))
                if not cursor.fetchone():
                    return redirect('/painel') # Não é do usuário

                # 2. Atualiza o animal (filtro user_id no UPDATE)
                sql = "UPDATE animais SET data_venda = %s, preco_venda = %s WHERE id = %s AND user_id = %s"
                cursor.execute(sql, (data_venda, preco_final, id_animal, current_user.id))
                
                # 3. Registra peso final
                cursor.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", (id_animal, data_venda, peso_venda))
                
            return redirect(f"/animal/{id_animal}")
        
        except ConnectionError:
            # Em um cenário real, você retornaria uma mensagem de erro ao usuário
            print("Erro de conexão ao vender animal.")
            return redirect(f"/animal/{id_animal}")
        except Exception as e:
            print(f"Erro ao vender animal: {e}")
            return redirect(f"/animal/{id_animal}")

    # GET: Verifica a propriedade antes de renderizar o formulário
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id FROM animais WHERE id = %s AND user_id = %s", (id_animal, current_user.id))
            if not cursor.fetchone():
                return redirect('/painel')
    except:
        return redirect('/painel') # Falha na conexão ou erro

    return render_template('vender.html', id_animal=id_animal)

@app.route('/medicar/<int:id_animal>', methods=['GET', 'POST'])
@login_required
def medicar(id_animal):
    """Registra a aplicação de medicamento em um animal."""
    
    # Valida dono (segurança) - Otimização: Faz a validação apenas uma vez no GET e no POST
    don_exists = False
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id FROM animais WHERE id = %s AND user_id = %s", (id_animal, current_user.id))
            if cursor.fetchone():
                don_exists = True
    except:
        return redirect('/painel') # Falha na conexão ou erro

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
            print("Erro de conexão ao medicar animal.")
            return redirect(f"/animal/{id_animal}")
        except Exception as e:
            print(f"Erro ao medicar animal: {e}")
            return redirect(f"/animal/{id_animal}")

    return render_template('medicar.html', id_animal=id_animal)

@app.route('/pesar/<int:id_animal>', methods=['GET', 'POST'])
@login_required
def nova_pesagem(id_animal):
    """Registra uma nova pesagem para um animal."""
    
    # Valida dono (segurança) - Otimização: Faz a validação apenas uma vez no GET e no POST
    don_exists = False
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id FROM animais WHERE id = %s AND user_id = %s", (id_animal, current_user.id))
            if cursor.fetchone():
                don_exists = True
    except:
        return redirect('/painel') # Falha na conexão ou erro

    if not don_exists:
        return redirect('/painel')

    if request.method == 'POST':
        try:
            with get_db_cursor() as cursor:
                cursor.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", (id_animal, request.form['data_pesagem'], request.form['peso']))
            return redirect(f"/animal/{id_animal}")
        except ConnectionError:
            print("Erro de conexão ao pesar animal.")
            return redirect(f"/animal/{id_animal}")
        except Exception as e:
            print(f"Erro ao pesar animal: {e}")
            return redirect(f"/animal/{id_animal}")

    return render_template('nova_pesagem.html', id_animal=id_animal)

# ======================================================================
# 7. ROTAS DE MANUTENÇÃO/EXCLUSÃO
# ======================================================================

@app.route('/excluir_animal/<int:id_animal>')
@login_required
def excluir_animal(id_animal):
    """Exclui um animal e todos os seus registros associados (pesagens e medicações)."""
    try:
        with get_db_cursor() as cursor:
            # CRÍTICO: Verifica se o animal pertence ao usuário antes de apagar
            cursor.execute("SELECT id FROM animais WHERE id = %s AND user_id = %s", (id_animal, current_user.id))
            if cursor.fetchone():
                # Exclui registros filhos primeiro (pesagens e medicações)
                # Otimização: O MySQL deve ter FOREIGN KEY ON DELETE CASCADE, mas manter o DELETE explícito é mais seguro
                cursor.execute("DELETE FROM pesagens WHERE animal_id = %s", (id_animal,))
                cursor.execute("DELETE FROM medicacoes WHERE animal_id = %s", (id_animal,))
                # Exclui o animal
                cursor.execute("DELETE FROM animais WHERE id = %s", (id_animal,))
    except ConnectionError:
        print("Erro de conexão ao excluir animal.")
    except Exception as e:
        print(f"Erro ao excluir animal: {e}")
        
    return redirect("/painel")

@app.route('/excluir_pesagem/<int:id_pesagem>')
@login_required
def excluir_pesagem(id_pesagem):
    """Exclui uma pesagem específica, verificando a propriedade do animal."""
    animal_id = None
    try:
        with get_db_cursor() as cursor:
            
            # CRÍTICO: JOIN para verificar se a pesagem pertence a um animal que é do usuário logado
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
        print("Erro de conexão ao excluir pesagem.")
    except Exception as e:
        print(f"Erro ao excluir pesagem: {e}")
        
    if animal_id:
        return redirect(f"/animal/{animal_id}")
    return redirect("/painel")

# ======================================================================
# 8. EXECUÇÃO PRINCIPAL
# ======================================================================
if __name__ == '__main__':
    # Roda o servidor de desenvolvimento. O debug é controlado por variável de ambiente.
    app.run(debug=os.getenv('FLASK_DEBUG', 'False') == 'True')
