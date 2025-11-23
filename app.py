from flask import Flask, render_template, request, redirect 
from db_config import get_db_connection, close_db_connection

app = Flask(__name__)


@app.route('/')
def index():
    conn = get_db_connection()
    animais = []
    
    # Captura o que foi digitado na busca (se houver)
    termo_busca = request.args.get('busca')

    if conn:
        cursor = conn.cursor()
        
        if termo_busca:
            # LÓGICA DE BUSCA:
            # O símbolo % significa "qualquer coisa antes ou depois"
            # Se digitar "50", busca "%50%" -> acha A-50, 500, 150...
            sql = "SELECT * FROM animais WHERE brinco LIKE %s"
            val = (f"%{termo_busca}%", )
            cursor.execute(sql, val)
        else:
            # Se não tiver busca, traz tudo normal
            cursor.execute("SELECT * FROM animais")
            
        animais = cursor.fetchall()
        cursor.close()
        close_db_connection(conn)
    
    return render_template("index.html", lista_animais=animais)

@app.route('/financeiro')
def financeiro():
    conn = get_db_connection()
    dados = {
        'valor_rebanho': 0,
        'total_compras': 0,
        'total_med': 0,
        'despesas_totais': 0,
        'receitas': 0,
        'balanco': 0
    }

    if conn:
        cursor = conn.cursor()
        
        # 1. Valor do Rebanho em Estoque (Ativos)
        # Soma o preço de compra APENAS de quem não foi vendido (data_venda IS NULL)
        cursor.execute("SELECT SUM(preco_compra) FROM animais WHERE data_venda IS NULL")
        dados['valor_rebanho'] = cursor.fetchone()[0] or 0 
        
        # 2. Despesa com Compra de Gado (Histórico Total)
        cursor.execute("SELECT SUM(preco_compra) FROM animais")
        dados['total_compras'] = cursor.fetchone()[0] or 0

        # 3. Despesa com Medicamentos (Histórico Total)
        cursor.execute("SELECT SUM(custo) FROM medicacoes")
        dados['total_med'] = cursor.fetchone()[0] or 0

        # 4. Receita de Vendas
        cursor.execute("SELECT SUM(preco_venda) FROM animais WHERE data_venda IS NOT NULL")
        dados['receitas'] = cursor.fetchone()[0] or 0

        cursor.close()
        close_db_connection(conn)

        # Cálculos Finais
        dados['despesas_totais'] = dados['total_compras'] + dados['total_med']
        dados['balanco'] = dados['receitas'] - dados['despesas_totais']

    return render_template('financeiro.html', financeiro=dados)

@app.route('/vender/<int:id_animal>', methods=['GET', 'POST'])
def vender(id_animal):
    if request.method == 'POST':
        # 1. Captura dos dados
        data_venda_form = request.form['data_venda']
        
        # Conversão para números
        peso_venda_form = float(request.form['peso_venda'])
        valor_arroba_form = float(request.form['valor_arroba'])

        # 2. CÁLCULO FINANCEIRO (Regra: 1@ = 30kg)
        # Preço Final = (Peso / 30) * Valor @
        preco_final = (peso_venda_form / 30) * valor_arroba_form

        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                
                # Ação 1: Atualizar o registro do animal (Baixa)
                sql_venda = "UPDATE animais SET data_venda = %s, preco_venda = %s WHERE id = %s"
                val_venda = (data_venda_form, preco_final, id_animal)
                cursor.execute(sql_venda, val_venda)

                # Ação 2: Inserir o peso final no histórico (Para o gráfico ficar completo)
                sql_peso = "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)"
                val_peso = (id_animal, data_venda_form, peso_venda_form)
                cursor.execute(sql_peso, val_peso)
                
                cursor.close()
            except Exception as e:
                print(f"Erro ao vender: {e}")
            finally:
                close_db_connection(conn)
            
            return redirect(f"/animal/{id_animal}")

    return render_template('vender.html', id_animal=id_animal)

@app.route('/animal/<int:id_animal>')
def ver_animal(id_animal):
    conn = get_db_connection()
    
    # Inicializamos as variáveis
    animal = None
    pesagens = []
    medicacoes = []
    
    # Dicionário de Indicadores (KPIs)
    kpis = {
        'peso_atual': 0,
        'ganho_total': 0,
        'custo_total': 0.00  # <--- Mudamos de 'qtd_pesagens' para 'custo_total'
    }

    if conn:
        cursor = conn.cursor()
        
        # 1. Dados do Animal
        cursor.execute("SELECT * FROM animais WHERE id = %s", (id_animal, ))
        animal = cursor.fetchone()

        # 2. Pesagens
        cursor.execute("SELECT * FROM pesagens WHERE animal_id = %s ORDER BY data_pesagem DESC", (id_animal, ))
        pesagens = cursor.fetchall()

        # 3. Medicações
        cursor.execute("SELECT * FROM medicacoes WHERE animal_id = %s", (id_animal, ))
        medicacoes = cursor.fetchall()

        cursor.close()
        close_db_connection(conn)

    # --- LÓGICA DE PESO ---
    if pesagens: 
        kpis['peso_atual'] = pesagens[0][3]
        kpis['ganho_total'] = pesagens[0][3] - pesagens[-1][3]

    # --- LÓGICA FINANCEIRA   ---
    if animal:
        # 1. Pega o preço de compra (Índice 4 da tabela animais)
        custo_compra = float(animal[4]) if animal[4] else 0.0
        
        # 2. Soma os custos das medicações
        # (Percorre a lista 'medicacoes' somando o Índice 4, que é o custo)
        custo_sanitario = 0.0
        for med in medicacoes:
            if med[4]: # Se tiver valor cadastrado
                custo_sanitario += float(med[4])
        
        # 3. Soma tudo
        kpis['custo_total'] = custo_compra + custo_sanitario

    # Formata para mostrar com 2 casas decimais bonitinhas (Opcional, mas recomendado)
    kpis['custo_total'] = f"{kpis['custo_total']:.2f}"

    return render_template("detalhes.html", 
                           animal=animal, 
                           historico_peso=pesagens, 
                           historico_med=medicacoes, 
                           indicadores=kpis)

@app.route('/excluir_animal/<int:id_animal>')
def excluir_animal(id_animal):
    conn = get_db_connection()
    
    if conn:
        try:
            cursor = conn.cursor()
            
            # 1. Remover histórico de PESO (Filhos)
            cursor.execute("DELETE FROM pesagens WHERE animal_id = %s", (id_animal,))
            
            # 2. Remover histórico SANITÁRIO (Filhos)
            cursor.execute("DELETE FROM medicacoes WHERE animal_id = %s", (id_animal,))
            
            # 3. Remover o ANIMAL (Pai)
            cursor.execute("DELETE FROM animais WHERE id = %s", (id_animal,))
            
            cursor.close()
        except Exception as e:
            print(f"Erro ao excluir: {e}")
        finally:
            close_db_connection(conn)
    
    # Após apagar, volta para a listagem geral (Menu)
    return redirect("/")

@app.route('/excluir_pesagem/<int:id_pesagem>')
def excluir_pesagem(id_pesagem):
    conn = get_db_connection()
    animal_id = None

    if conn:
        try:
            cursor = conn.cursor()

            
            cursor.execute("SELECT animal_id FROM pesagens WHERE id = %s", (id_pesagem,))
            resultado = cursor.fetchone()
            
            if resultado:
                animal_id = resultado[0]
                
                
                cursor.execute("DELETE FROM pesagens WHERE id = %s", (id_pesagem,))
                
            
            cursor.close()
        except Exception as e:
            print(f"Erro ao excluir: {e}")
        finally:
            close_db_connection(conn)
    
    
    if animal_id:
        return redirect(f"/animal/{animal_id}")
    else:
        return redirect("/")

    

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    mensagem = None
    
    if request.method == "POST":
        # 1. Captura dos dados do formulário
        brinco_form = request.form["brinco"]
        sexo_form = request.form["sexo"]
        data_form = request.form["data_compra"]
        
        # Convertendo textos para números decimais (float) para fazer contas
        peso_form = float(request.form["peso_compra"])
        valor_arroba_form = float(request.form["valor_arroba"])

        # 2. CÁLCULO FINANCEIRO (Regra: 1@ = 30kg)
        # Descobrimos quantas arrobas tem o animal e multiplicamos pelo preço da @
        preco_calculado = (peso_form / 30) * valor_arroba_form

        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                
                # 3. Inserção na tabela ANIMAIS
                # O campo 'preco_compra' recebe o valor calculado matematicamente acima
                sql_animal = "INSERT INTO animais (brinco, sexo, data_compra, preco_compra) VALUES (%s, %s, %s, %s)"
                val_animal = (brinco_form, sexo_form, data_form, preco_calculado)
                cursor.execute(sql_animal, val_animal)
                
                # Captura o ID do animal que acabou de ser criado
                id_novo_animal = cursor.lastrowid
                
                # 4. Inserção na tabela PESAGENS (Registro do peso inicial)
                sql_peso = "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)"
                val_peso = (id_novo_animal, data_form, peso_form)
                cursor.execute(sql_peso, val_peso)
                
                # Mensagem de confirmação mostrando o valor calculado
                mensagem = f"Sucesso! Animal salvo. Custo calculado: R$ {preco_calculado:.2f} (Baseado em {valor_arroba_form} por @)"
                cursor.close()
                
            except Exception as e:
                mensagem = f"Erro ao salvar: {e}"
            finally:
                close_db_connection(conn)
    
    # Esta linha deve estar fora do IF para carregar a página inicialmente
    return render_template("cadastro.html", mensagem=mensagem)

@app.route('/medicar/<int:id_animal>', methods=['GET', 'POST'])
def medicar(id_animal):
    if request.method == 'POST':
        data_app = request.form['data_aplicacao']
        nome = request.form['nome']
        custo = request.form['custo']
        obs = request.form['obs']

        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                sql = """INSERT INTO medicacoes 
                         (animal_id, data_aplicacao, nome_medicamento, custo, observacoes) 
                         VALUES (%s, %s, %s, %s, %s)"""
                val = (id_animal, data_app, nome, custo, obs)
                cursor.execute(sql, val)
                cursor.close()
            except Exception as e:
                print(f"Erro: {e}")
            finally:
                close_db_connection(conn)
            
            return redirect(f"/animal/{id_animal}")

    return render_template('medicar.html', id_animal=id_animal)

@app.route('/pesar/<int:id_animal>', methods=['GET', 'POST'])
def pesar(id_animal):
    if request.method == 'POST':
        data_peso = request.form['data_pesagem']
        peso_novo = request.form['peso']

        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                # Inserindo na tabela pesagens
                sql = "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)"
                val = (id_animal, data_peso, peso_novo)
                cursor.execute(sql, val)
                cursor.close()
            except Exception as e:
                print(f"Erro: {e}")
            finally:
                close_db_connection(conn)
            
            return redirect(f"/animal/{id_animal}")

    return render_template('nova_pesagem.html', id_animal=id_animal)
if __name__ == '__main__':
    app.run(debug=True)