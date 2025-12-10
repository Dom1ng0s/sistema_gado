import mysql.connector
import os
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env (CRÍTICO para conexões cloud)
load_dotenv()

def obter_configuracao():
    """Busca credenciais seguras do ambiente."""
    print("--- 📡 CONFIGURAÇÃO DE CONEXÃO ---")
    host = os.getenv('DB_HOST')
    user = os.getenv('DB_USER')
    db_name = os.getenv('DB_NAME')
    
    # Debug Seguro (Mostra onde está tentando conectar sem vazar senha)
    print(f"Host Alvo: {host}")
    print(f"Usuário: {user}")
    print(f"Banco de Dados: {db_name}")
    
    if not host or not user or not db_name:
        raise ValueError("❌ ERRO: Verifique seu arquivo .env. Faltam variáveis (DB_HOST, DB_USER ou DB_NAME).")

    return {
        'host': host,
        'user': user,
        'password': os.getenv('DB_PASSWORD'),
        'database': db_name,
        'port': int(os.getenv('DB_PORT', 3306))
    }

def configurar_banco_cloud():
    print("\n--- 🚀 INICIANDO SETUP (MODO CLOUD) ---")
    
    config = obter_configuracao()
    
    try:
        # Tenta conexão direta (Sem tentar criar Database, pois a Cloud já fornece)
        conn = mysql.connector.connect(**config)
        cursor = conn.cursor()
        print("✅ Conexão estabelecida com sucesso!")
        
        # 1. Tabelas (Idempotente: Só cria se não existir)
        tabelas = [
            """CREATE TABLE IF NOT EXISTS usuarios (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS animais (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                brinco VARCHAR(20) NOT NULL,
                sexo ENUM('M', 'F') NOT NULL,
                data_compra DATE NOT NULL,
                preco_compra DECIMAL(10,2),
                data_venda DATE,
                preco_venda DECIMAL(10,2),
                FOREIGN KEY (user_id) REFERENCES usuarios(id)
            )""",
            """CREATE TABLE IF NOT EXISTS pesagens (
                id INT AUTO_INCREMENT PRIMARY KEY,
                animal_id INT NOT NULL,
                data_pesagem DATE NOT NULL,
                peso DECIMAL(10,2) NOT NULL,
                FOREIGN KEY (animal_id) REFERENCES animais(id)
            )""",
            """CREATE TABLE IF NOT EXISTS medicacoes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                animal_id INT NOT NULL,
                data_aplicacao DATE NOT NULL,
                nome_medicamento VARCHAR(100),
                custo DECIMAL(10,2),
                observacoes TEXT,
                FOREIGN KEY (animal_id) REFERENCES animais(id)
            )""",
            """CREATE TABLE IF NOT EXISTS custos_operacionais (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                categoria VARCHAR(50),
                tipo_custo VARCHAR(50),
                valor DECIMAL(10,2),
                data_custo DATE,
                descricao TEXT,
                FOREIGN KEY (user_id) REFERENCES usuarios(id)
            )"""
        ]
        
        print("1. Validando estrutura de tabelas...")
        for query in tabelas:
            cursor.execute(query)

        # 2. View Analítica (A Inteligência do GMD)
        # NOTA: Alguns provedores cloud exigem permissões específicas para VIEWS.
        # Se der erro aqui, é permissão do seu usuário cloud.
        print("2. Atualizando View de Inteligência (GMD)...")
        
        # Dropamos a view antiga para garantir que a nova lógica seja aplicada
        cursor.execute("DROP VIEW IF EXISTS v_gmd_analitico")
        
        sql_view = """
        CREATE VIEW v_gmd_analitico AS
        WITH PesagensOrdenadas AS (
            SELECT 
                animal_id, 
                data_pesagem, 
                peso,
                ROW_NUMBER() OVER(PARTITION BY animal_id ORDER BY data_pesagem ASC) as rn_asc,
                ROW_NUMBER() OVER(PARTITION BY animal_id ORDER BY data_pesagem DESC) as rn_desc
            FROM pesagens
        ),
        PrimeiraUltima AS (
            SELECT 
                animal_id,
                MAX(CASE WHEN rn_asc = 1 THEN data_pesagem END) AS data_inicial,
                MAX(CASE WHEN rn_asc = 1 THEN peso END) AS peso_inicial,
                MAX(CASE WHEN rn_desc = 1 THEN data_pesagem END) AS data_final,
                MAX(CASE WHEN rn_desc = 1 THEN peso END) AS peso_final
            FROM PesagensOrdenadas
            GROUP BY animal_id
        )
        SELECT 
            a.user_id,
            a.id as animal_id,
            a.brinco,
            p.data_inicial,
            p.peso_inicial,
            p.data_final,
            p.peso_final,
            (p.peso_final - p.peso_inicial) as ganho_total,
            DATEDIFF(p.data_final, p.data_inicial) as dias,
            CASE 
                WHEN DATEDIFF(p.data_final, p.data_inicial) > 0 
                THEN (p.peso_final - p.peso_inicial) / DATEDIFF(p.data_final, p.data_inicial)
                ELSE 0 
            END as gmd
        FROM PrimeiraUltima p
        JOIN animais a ON p.animal_id = a.id
        WHERE p.data_inicial <> p.data_final;
        """
        cursor.execute(sql_view)
        
        conn.commit()
        print("✅ SUCESSO! Banco Cloud atualizado e pronto.")
        
    except mysql.connector.Error as err:
        print(f"\n❌ ERRO DE CONEXÃO OU SQL:")
        print(f"Código: {err.errno}")
        print(f"Mensagem: {err.msg}")
        print("\nDica: Verifique se o IP da sua máquina está liberado no firewall do banco cloud.")
    
    except Exception as e:
        print(f"\n❌ ERRO GERAL: {e}")
    
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    configurar_banco_cloud()