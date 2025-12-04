import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

print("Conectando ao banco na nuvem...")
try:
    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        port=int(os.getenv('DB_PORT', 3306))
    )
    cursor = conn.cursor()

    # 1. Tabela de ANIMAIS
    print("Criando tabela 'animais'...")
    sql_animais = """
    CREATE TABLE IF NOT EXISTS animais (
        id INT AUTO_INCREMENT PRIMARY KEY,
        brinco VARCHAR(50) NOT NULL,
        sexo CHAR(1) NOT NULL,
        data_compra DATE NOT NULL,
        preco_compra DECIMAL(10, 2),
        data_venda DATE,
        preco_venda DECIMAL(10, 2),
        user_id INT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES usuarios(id),
        UNIQUE KEY idx_brinco_user (brinco, user_id)
    );
    """
    cursor.execute(sql_animais)

    # 2. Tabela de PESAGENS
    print("Criando tabela 'pesagens'...")
    sql_pesagens = """
    CREATE TABLE IF NOT EXISTS pesagens (
        id INT AUTO_INCREMENT PRIMARY KEY,
        animal_id INT NOT NULL,
        data_pesagem DATE NOT NULL,
        peso DECIMAL(10, 2) NOT NULL,
        FOREIGN KEY (animal_id) REFERENCES animais(id)
    );
    """
    cursor.execute(sql_pesagens)

    # 3. Tabela de MEDICAÇÕES
    print("Criando tabela 'medicacoes'...")
    sql_medicacoes = """
    CREATE TABLE IF NOT EXISTS medicacoes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        animal_id INT NOT NULL,
        data_aplicacao DATE NOT NULL,
        nome_medicamento VARCHAR(100) NOT NULL,
        custo DECIMAL(10, 2),
        observacoes TEXT,
        FOREIGN KEY (animal_id) REFERENCES animais(id)
    );
    """
    cursor.execute(sql_medicacoes)

    print("Criando tabela 'custos_operacionais'...")
    sql_custos = """
    CREATE TABLE IF NOT EXISTS custos_operacionais (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        categoria VARCHAR(20) NOT NULL,  -- 'Fixo' ou 'Variavel'
        tipo_custo VARCHAR(50) NOT NULL, -- Ex: 'Salário' ou o que o usuário digitar
        valor DECIMAL(10, 2) NOT NULL,
        data_custo DATE NOT NULL,
        descricao TEXT,
        FOREIGN KEY (user_id) REFERENCES usuarios(id)
    );
    """
    cursor.execute(sql_custos)


    conn.commit()
    cursor.close()
    conn.close()
    print("\n✅ SUCESSO! Todas as tabelas foram criadas no banco online.")

except Exception as e:
    print(f"\n❌ ERRO: {e}")