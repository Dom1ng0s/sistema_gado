from flask import Flask, render_template, request
from db_config import get_db_connection, close_db_connection

app = Flask(__name__)


@app.route('/')
def index():
    conn = get_db_connection()
    animais = []

    if conn:
        cursor = conn.cursor()
        cursor.execute("select * from animais")
        animais = cursor.fetchall()
        cursor.close()
        close_db_connection(conn)
    return render_template("index.html",lista_animais = animais)

@app.route('/animal/<int:id_animal>')
def ver_animal(id_animal):
    conn = get_db_connection()
    animal = None
    pesagens = []

    if conn:
        cursor = conn.cursor()
        cursor.execute("select * from animais where id = %s",(id_animal))
        animal = cursor.fetchone()

        cursor.execute("select * from pesagens where animal_id = %s",(id_animal))
        pesagens = cursor.fetchall()

        cursor.close()
        
        close_db_connection(conn)
        return render_template("detalhes.html", animal=animal, historico_peso=pesagens)


    
@app.route("/cadastro",methods=["GET","POST"])
def cadastro():
    mensagem = None
    if request.method == "POST":
        brinco_form = request.form["brinco"]
        sexo_form = request.form["sexo"]
        data_form = request.form["data_compra"]
        preco_form = request.form["preco_compra"]
        peso_form = request.form["peso_compra"]

        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                
                sql_animal = "INSERT INTO animais (brinco, sexo, data_compra, preco_compra) VALUES (%s, %s, %s, %s)"
                val_animal = (brinco_form, sexo_form, data_form, preco_form)
                cursor.execute(sql_animal, val_animal)
                
                id_novo_animal = cursor.lastrowid
                
                sql_peso = "INSERT INTO pesagens (animal_id, data_pesagem, peso) VALUES (%s, %s, %s)"
                val_peso = (id_novo_animal, data_form, peso_form)
                cursor.execute(sql_peso, val_peso)
                
                mensagem = f"Sucesso! Animal {brinco_form} cadastrado com peso inicial."
                cursor.close()
                
            except Exception as e:
                mensagem = f"Erro ao salvar: {e}"
            finally:
                close_db_connection(conn)