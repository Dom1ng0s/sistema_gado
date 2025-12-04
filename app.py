import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from db_config import get_db_connection, close_db_connection
from contextlib import contextmanager
from datetime import date


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
    """Exibe a lista de animais do usuário logado, com opção de busca."""
    animais = []
    termo_busca = request.args.get('busca')

    try:
        with get_db_cursor() as cursor:
            # Lógica Multi-Tenant: CRÍTICO - Sempre filtrar por user_id = current_user.id
            if termo_busca:
                sql = "SELECT id, brinco, sexo, data_compra, preco_compra, data_venda, preco_venda FROM animais WHERE brinco LIKE %s AND user_id = %s"
                val = (f"%{termo_busca}%", current_user.id)
                cursor.execute(sql, val)
            else:
                sql = "SELECT id, brinco, sexo, data_compra, preco_compra, data_venda, preco_venda FROM animais WHERE user_id = %s ORDER BY brinco ASC"
                val = (current_user.id,)
                cursor.execute(sql, val)
                
            # Otimização: Retorna como tupla para manter a compatibilidade com o template index.html
            animais = cursor.fetchall()
            
    except ConnectionError:
        # Em caso de erro de conexão, retorna lista vazia e o template deve lidar com isso
        pass
    except Exception as e:
        print(f"Erro ao buscar animais: {e}")
    
    return render_template("index.html", lista_animais=animais)

@app.route('/financeiro')
@login_required
def financeiro():
    """
    Calcula e exibe o painel financeiro do usuário logado.
    OTIMIZAÇÃO: Agrupa todas as consultas de agregação em uma única conexão.
    """
    dados = {
        'valor_rebanho': 0, 'total_compras': 0, 'total_med': 0,
        'despesas_totais': 0, 'receitas': 0, 'balanco': 0
    }

    try:
        with get_db_cursor() as cursor:
            uid = current_user.id # ID do usuário logado
            
            # 1. Valor do Rebanho (Animais não vendidos)
            cursor.execute("SELECT SUM(preco_compra) FROM animais WHERE data_venda IS NULL AND user_id = %s", (uid,))
            dados['valor_rebanho'] = cursor.fetchone()[0] or 0 
            
            # 2. Total de Compras (Custo de aquisição de todos os animais)
            cursor.execute("SELECT SUM(preco_compra) FROM animais WHERE user_id = %s", (uid,))
            dados['total_compras'] = cursor.fetchone()[0] or 0
            
            # 3. Total de Receitas (Vendas)
            cursor.execute("SELECT SUM(preco_venda) FROM animais WHERE data_venda IS NOT NULL AND user_id = %s", (uid,))
            dados['receitas'] = cursor.fetchone()[0] or 0

            # 4. Total de Medicação (Consulta com JOIN)
            cursor.execute("""
                SELECT SUM(m.custo) FROM medicacoes m 
                JOIN animais a ON m.animal_id = a.id 
                WHERE a.user_id = %s
            """, (uid,))
            dados['total_med'] = cursor.fetchone()[0] or 0
            
    except ConnectionError:
        # Em caso de erro de conexão, os valores permanecem 0
        pass
    except Exception as e:
        print(f"Erro no financeiro: {e}")

    # Cálculos finais
    dados['despesas_totais'] = dados['total_compras'] + dados['total_med']
    dados['balanco'] = dados['receitas'] - dados['despesas_totais']

    return render_template('financeiro.html', financeiro=dados)

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
    """Processa as contagens no banco e retorna JSON para o gráfico."""
    try:
        with get_db_cursor() as cursor:
            uid = current_user.id
            
            # --- 1. DADOS DE SEXO (Agregação via SQL) ---
            # Conta bois vs vacas ativos
            cursor.execute("""
                SELECT sexo, COUNT(*) 
                FROM animais 
                WHERE user_id = %s AND data_venda IS NULL 
                GROUP BY sexo
            """, (uid,))
            resultado_sexo = cursor.fetchall()
            dados_sexo = {sexo: qtd for sexo, qtd in resultado_sexo}
            
            # --- 2. DADOS DE PESO (Lógica Mista) ---
            # Busca apenas o PESO MAIS RECENTE de cada animal ativo
            cursor.execute("""
                SELECT p.peso 
                FROM pesagens p
                INNER JOIN (
                    SELECT animal_id, MAX(id) as max_id
                    FROM pesagens
                    GROUP BY animal_id
                ) ultimas ON p.id = ultimas.max_id
                INNER JOIN animais a ON p.animal_id = a.id
                WHERE a.user_id = %s AND a.data_venda IS NULL
            """, (uid,))
            pesos_brutos = cursor.fetchall()

            # Categorização das Arrobas (Lógica Python)
            categorias = {
                'Menos de 10@': 0, '10@ a 15@': 0, 
                '15@ a 20@': 0, 'Mais de 20@': 0
            }

            for (peso_kg,) in pesos_brutos:
                peso_arroba = float(peso_kg) / 30
                if peso_arroba < 10: categorias['Menos de 10@'] += 1
                elif 10 <= peso_arroba < 15: categorias['10@ a 15@'] += 1
                elif 15 <= peso_arroba < 20: categorias['15@ a 20@'] += 1
                else: categorias['Mais de 20@'] += 1

            # Retorna o JSON final
            return jsonify({'sexo': dados_sexo, 'peso': categorias})

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

@app.route('/custos_operacionais')
@login_required
def custosoperacionais():
    print("Cheguei")

@app.route('/animal/<int:id_animal>')
@login_required
def detalhes(id_animal):
    """
    Exibe os detalhes, histórico de peso e medicação de um animal específico.
    OTIMIZAÇÃO: Agrupa todas as consultas em uma única conexão.
    """
    animal, pesagens, medicacoes = None, [], []
    kpis = {'peso_atual': 0, 'ganho_total': 0, 'custo_total': "0.00"}

    try:
        with get_db_cursor() as cursor:
            
            # 1. BUSCA SEGURA: Só retorna se o animal pertencer ao usuário logado
            cursor.execute("SELECT * FROM animais WHERE id = %s AND user_id = %s", (id_animal, current_user.id))
            animal = cursor.fetchone()
            
            if animal:
                # 2. Busca histórico de pesagens
                cursor.execute("SELECT * FROM pesagens WHERE animal_id = %s ORDER BY data_pesagem DESC", (id_animal,))
                pesagens = cursor.fetchall()
                
                # 3. Busca histórico de medicações
                cursor.execute("SELECT * FROM medicacoes WHERE animal_id = %s", (id_animal,))
                medicacoes = cursor.fetchall()
        
    except ConnectionError:
        # Em caso de erro de conexão, retorna None e listas vazias
        pass
    except Exception as e:
        print(f"Erro nos detalhes do animal: {e}")

    # Se não encontrou ou não é dono, redireciona para o painel (segurança)
    if not animal:
        return redirect('/painel')

    # Cálculos de KPIs
    if pesagens: 
        # Otimização: A pesagem mais recente é a primeira da lista (ORDER BY DESC)
        peso_atual = pesagens[0][3] # Coluna 'peso'
        peso_inicial = pesagens[-1][3] # Coluna 'peso'
        kpis['peso_atual'] = peso_atual
        kpis['ganho_total'] = peso_atual - peso_inicial

    custo_compra = float(animal[4]) if animal[4] else 0.0 # Coluna 'preco_compra'
    custo_sanitario = sum(float(m[4]) for m in medicacoes if m[4]) # Coluna 'custo'
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
