import os
from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from db_config import get_db_connection, close_db_connection

# ======================================================================
# 1. INICIALIZAÇÃO DO APP E CONFIGURAÇÃO DE SEGURANÇA
# ======================================================================
app = Flask(__name__)

# Chave secreta usada para assinar cookies de sessão.
# CRÍTICO: Em produção, o fallback 'chave_desenvolvimento_segura_123' deve ser removido.
app.secret_key = os.getenv('SECRET_KEY', 'chave_desenvolvimento_segura_123')

# ======================================================================
# 2. CONFIGURAÇÃO DO FLASK-LOGIN
# ======================================================================
login_manager = LoginManager()
login_manager.init_app(app)
# Define a rota para onde o usuário é redirecionado se tentar acessar uma página protegida sem login.
login_manager.login_view = 'login'

# ======================================================================
# 3. MODELO DE USUÁRIO E USER LOADER
# Define a classe User para ser usada pelo Flask-Login.
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
            cursor = conn.cursor()
            # Busca o usuário na tabela 'usuarios'
            cursor.execute("SELECT * FROM usuarios WHERE id = %s", (user_id,))
            dados = cursor.fetchone()
            cursor.close()
            close_db_connection(conn)
            if dados:
                # Retorna uma instância da classe User
                return User(dados[0], dados[1], dados[2])
        return None

@login_manager.user_loader
def load_user(user_id):
    """Função obrigatória para recarregar o objeto User a partir do ID de sessão."""
    return User.get_user_id(user_id)

# ======================================================================
# 4. ROTAS DE AUTENTICAÇÃO E NAVEGAÇÃO BÁSICA
# Controlam o acesso ao sistema.
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
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            # Busca o usuário pelo nome
            cursor.execute("SELECT * FROM usuarios WHERE username = %s", (username,))
            dados = cursor.fetchone()
            cursor.close()
            close_db_connection(conn)
            
            if dados:
                user_obj = User(dados[0], dados[1], dados[2])
                # Verifica o hash da senha usando werkzeug.security
                if check_password_hash(user_obj.password_hash, password):
                    login_user(user_obj)
                    return redirect('/painel')
        
        return render_template('login.html', mensagem="Usuário ou senha incorretos")
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Desloga o usuário e o redireciona para a página de login."""
    logout_user()
    return redirect('/login')

@app.route('/novo_usuario', methods=['GET', 'POST'])
@login_required
def novo_usuario():
    """Permite a criação de novos usuários (apenas por usuários já logados)."""
    mensagem = None
    if request.method == 'POST':
        novo_user = request.form['username'].strip()
        nova_senha = request.form['password'].strip()
        
        if not novo_user or not nova_senha:
             return render_template('novo_usuario.html', mensagem="Preencha todos os campos.")

        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                # Verifica se o usuário já existe
                cursor.execute("SELECT id FROM usuarios WHERE username = %s", (novo_user,))
                if cursor.fetchone():
                    mensagem = f"Erro: Usuário '{novo_user}' já existe."
                else:
                    # Gera o hash seguro da senha
                    hash_senha = generate_password_hash(nova_senha)
                    cursor.execute("INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)", (novo_user, hash_senha))
                    mensagem = f"Sucesso! Usuário '{novo_user}' criado."
                cursor.close()
            except Exception as e:
                mensagem = f"Erro: {e}"
            finally:
                close_db_connection(conn)
    return render_template('novo_usuario.html', mensagem=mensagem)

# ======================================================================
# 5. ROTAS PRINCIPAIS DA APLICAÇÃO (PROTEGIDAS E FILTRADAS POR USUÁRIO)
# Controlam o CRUD e relatórios do sistema.
# ======================================================================

@app.route('/painel')
@login_required
def painel():
    """Exibe a lista de animais do usuário logado, com opção de busca."""
    conn = get_db_connection()
    animais = []
    termo_busca = request.args.get('busca')

    if conn:
        cursor = conn.cursor()
        
        # Lógica Multi-Tenant: CRÍTICO - Sempre filtrar por user_id = current_user.id
        if termo_busca:
            sql = "SELECT * FROM animais WHERE brinco LIKE %s AND user_id = %s"
            val = (f"%{termo_busca}%", current_user.id)
            cursor.execute(sql, val)
        else:
            sql = "SELECT * FROM animais WHERE user_id = %s"
            val = (current_user.id,)
            cursor.execute(sql, val)
            
        animais = cursor.fetchall()
        cursor.close()
        close_db_connection(conn)
    
    return render_template("index.html", lista_animais=animais)

@app.route('/financeiro')
@login_required
def financeiro():
    """Calcula e exibe o painel financeiro do usuário logado."""
    conn = get_db_connection()
    dados = {
        'valor_rebanho': 0, 'total_compras': 0, 'total_med': 0,
        'despesas_totais': 0, 'receitas': 0, 'balanco': 0
    }

    if conn:
        cursor = conn.cursor()
        uid = current_user.id # ID do usuário logado
        
        # Todas as consultas são filtradas pelo user_id (uid)
        cursor.execute("SELECT SUM(preco_compra) FROM animais WHERE data_venda IS NULL AND user_id = %s", (uid,))
        dados['valor_rebanho'] = cursor.fetchone()[0] or 0 
        
        cursor.execute("SELECT SUM(preco_compra) FROM animais WHERE user_id = %s", (uid,))
        dados['total_compras'] = cursor.fetchone()[0] or 0

        # Consulta com JOIN para garantir que só soma medicação de animais do usuário
        cursor.execute("""
            SELECT SUM(m.custo) FROM medicacoes m 
            JOIN animais a ON m.animal_id = a.id 
            WHERE a.user_id = %s
        """, (uid,))
        dados['total_med'] = cursor.fetchone()[0] or 0

        cursor.execute("SELECT SUM(preco_venda) FROM animais WHERE data_venda IS NOT NULL AND user_id = %s", (uid,))
        dados['receitas'] = cursor.fetchone()[0] or 0

        cursor.close()
        close_db_connection(conn)

        dados['despesas_totais'] = dados['total_compras'] + dados['total_med']
        dados['balanco'] = dados['receitas'] - dados['despesas_totais']

    return render_template('financeiro.html', financeiro=dados)

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

            conn = get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    
                    # Verifica se brinco já existe PARA ESTE USUÁRIO (Multi-Tenant Check)
                    cursor.execute("SELECT id FROM animais WHERE brinco = %s AND user_id = %s", (brinco, current_user.id))
                    if cursor.fetchone():
                         cursor.close()
                         return render_template("cadastro.html", mensagem=f"Erro: O brinco {brinco} já existe no seu rebanho.")

                    # Insere o animal, vinculando-o ao usuário logado (current_user.id)
                    sql = "INSERT INTO animais (brinco, sexo, data_compra, preco_compra, user_id) VALUES (%s, %s, %s, %s, %s)"
                    val = (brinco, sexo, data, preco_calc, current_user.id)
                    cursor.execute(sql, val)
                    id_animal = cursor.lastrowid
                    
                    # Registra peso inicial
                    cursor.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", (id_animal, data, peso))
                    
                    mensagem = f"Sucesso! Animal {brinco} cadastrado."
                    cursor.close()
                except Exception as e:
                    mensagem = f"Erro BD: {e}"
                finally:
                    close_db_connection(conn)
        except Exception as e:
            mensagem = f"Erro Inesperado: {e}"
    
    return render_template("cadastro.html", mensagem=mensagem)

@app.route('/animal/<int:id_animal>')
@login_required
def detalhes(id_animal):
    """Exibe os detalhes, histórico de peso e medicação de um animal específico."""
    conn = get_db_connection()
    animal, pesagens, medicacoes = None, [], []
    kpis = {'peso_atual': 0, 'ganho_total': 0, 'custo_total': "0.00"}

    if conn:
        cursor = conn.cursor()
        
        # BUSCA SEGURA: Só retorna se o animal pertencer ao usuário logado
        cursor.execute("SELECT * FROM animais WHERE id = %s AND user_id = %s", (id_animal, current_user.id))
        animal = cursor.fetchone()

        if animal:
            # Se o animal é do usuário, busca seus históricos
            cursor.execute("SELECT * FROM pesagens WHERE animal_id = %s ORDER BY data_pesagem DESC", (id_animal,))
            pesagens = cursor.fetchall()
            cursor.execute("SELECT * FROM medicacoes WHERE animal_id = %s", (id_animal,))
            medicacoes = cursor.fetchall()
        
        cursor.close()
        close_db_connection(conn)

    # Se não encontrou ou não é dono, redireciona para o painel (segurança)
    if not animal:
        return redirect('/painel')

    # Cálculos de KPIs
    if pesagens: 
        kpis['peso_atual'] = pesagens[0][3]
        kpis['ganho_total'] = pesagens[0][3] - pesagens[-1][3]

    custo_compra = float(animal[4]) if animal[4] else 0.0
    custo_sanitario = sum(float(m[4]) for m in medicacoes if m[4])
    kpis['custo_total'] = f"{custo_compra + custo_sanitario:.2f}"

    return render_template("detalhes.html", animal=animal, historico_peso=pesagens, historico_med=medicacoes, indicadores=kpis)

@app.route('/vender/<int:id_animal>', methods=['GET', 'POST'])
@login_required
def vender(id_animal):
    """Processa a venda de um animal, atualizando o registro e registrando o peso final."""
    # Verificação de segurança (Propriedade)
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        # Verifica se o animal pertence ao usuário logado
        cursor.execute("SELECT id FROM animais WHERE id = %s AND user_id = %s", (id_animal, current_user.id))
        if not cursor.fetchone():
            cursor.close()
            close_db_connection(conn)
            return redirect('/painel')
        cursor.close()
        close_db_connection(conn)

    if request.method == 'POST':
        data_venda = request.form['data_venda']
        peso_venda = float(request.form['peso_venda'])
        valor_arroba = float(request.form['valor_arroba'])
        preco_final = (peso_venda / 30) * valor_arroba

        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                # Atualiza apenas se for meu animal (filtro user_id no UPDATE)
                sql = "UPDATE animais SET data_venda = %s, preco_venda = %s WHERE id = %s AND user_id = %s"
                cursor.execute(sql, (data_venda, preco_final, id_animal, current_user.id))
                
                # Registra peso final
                cursor.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", (id_animal, data_venda, peso_venda))
                cursor.close()
            finally:
                close_db_connection(conn)
            return redirect(f"/animal/{id_animal}")

    return render_template('vender.html', id_animal=id_animal)

@app.route('/medicar/<int:id_animal>', methods=['GET', 'POST'])
@login_required
def medicar(id_animal):
    """Registra a aplicação de medicamento em um animal."""
    conn = get_db_connection()
    don_exists = False
    
    # Valida dono (segurança)
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM animais WHERE id = %s AND user_id = %s", (id_animal, current_user.id))
        if cursor.fetchone():
            don_exists = True
        cursor.close()
        close_db_connection(conn)
    
    if not don_exists:
        return redirect('/painel')

    if request.method == 'POST':
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                sql = "INSERT INTO medicacoes (animal_id, data_aplicacao, nome_medicamento, custo, observacoes) VALUES (%s, %s, %s, %s, %s)"
                val = (id_animal, request.form['data_aplicacao'], request.form['nome'], request.form['custo'], request.form['obs'])
                cursor.execute(sql, val)
                cursor.close()
            finally:
                close_db_connection(conn)
            return redirect(f"/animal/{id_animal}")

    return render_template('medicar.html', id_animal=id_animal)

@app.route('/pesar/<int:id_animal>', methods=['GET', 'POST'])
@login_required
def nova_pesagem(id_animal):
    """Registra uma nova pesagem para um animal."""
    conn = get_db_connection()
    don_exists = False
    
    # Valida dono (segurança)
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM animais WHERE id = %s AND user_id = %s", (id_animal, current_user.id))
        if cursor.fetchone():
            don_exists = True
        cursor.close()
        close_db_connection(conn)
    
    if not don_exists:
        return redirect('/painel')

    if request.method == 'POST':
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)", (id_animal, request.form['data_pesagem'], request.form['peso']))
                cursor.close()
            finally:
                close_db_connection(conn)
            return redirect(f"/animal/{id_animal}")

    return render_template('nova_pesagem.html', id_animal=id_animal)

# ======================================================================
# 6. ROTAS DE MANUTENÇÃO/EXCLUSÃO
# Controlam a remoção de dados.
# ======================================================================

@app.route('/excluir_animal/<int:id_animal>')
@login_required
def excluir_animal(id_animal):
    """Exclui um animal e todos os seus registros associados (pesagens e medicações)."""
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            # CRÍTICO: Verifica se o animal pertence ao usuário antes de apagar
            cursor.execute("SELECT id FROM animais WHERE id = %s AND user_id = %s", (id_animal, current_user.id))
            if cursor.fetchone():
                # Exclui registros filhos primeiro (pesagens e medicações)
                cursor.execute("DELETE FROM pesagens WHERE animal_id = %s", (id_animal,))
                cursor.execute("DELETE FROM medicacoes WHERE animal_id = %s", (id_animal,))
                # Exclui o animal
                cursor.execute("DELETE FROM animais WHERE id = %s", (id_animal,))
            cursor.close()
        except Exception as e:
            print(f"Erro: {e}")
        finally:
            close_db_connection(conn)
    return redirect("/painel")

@app.route('/excluir_pesagem/<int:id_pesagem>')
@login_required
def excluir_pesagem(id_pesagem):
    """Exclui uma pesagem específica, verificando a propriedade do animal."""
    conn = get_db_connection()
    animal_id = None
    if conn:
        try:
            cursor = conn.cursor()
            
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
            
            cursor.close()
        except Exception as e:
            print(f"Erro: {e}")
        finally:
            close_db_connection(conn)
    
    if animal_id:
        return redirect(f"/animal/{animal_id}")
    return redirect("/painel")

# ======================================================================
# 7. EXECUÇÃO PRINCIPAL
# ======================================================================
if __name__ == '__main__':
    # Roda o servidor de desenvolvimento. O debug é controlado por variável de ambiente.
    app.run(debug=os.getenv('FLASK_DEBUG', 'False') == 'True')
