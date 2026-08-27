"""Bootstrap do banco: aplica as migrations versionadas e (opcional) cria o admin.

O schema NÃO vive mais aqui — ele está em ``migrations/*.sql``, aplicado pelo
``db_migrate.py`` (fina camada sobre yoyo-migrations). Este script continua sendo
o ``preDeployCommand`` do Railway: idempotente, roda a cada deploy.

    python init_db.py       # aplica migrations pendentes + seed opcional do admin
"""
import os
import sys
import time

import mysql.connector
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

from db_migrate import apply_migrations

load_dotenv()


def _seed_admin():
    """Cria o usuário 'admin' se SEED_ADMIN=true (bootstrap de ambiente local).

    O preDeployCommand roda a cada deploy — por isso é opt-in e exige senha
    explícita, para não semear uma conta conhecida em produção.
    """
    if os.getenv('SEED_ADMIN') != 'true':
        return
    senha = os.getenv('ADMIN_PASSWORD')
    if not senha:
        raise RuntimeError("SEED_ADMIN=true exige ADMIN_PASSWORD definido no ambiente.")

    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        port=int(os.getenv('DB_PORT', 3306)),
        connection_timeout=10,
    )
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
            ('admin', generate_password_hash(senha)),
        )
        conn.commit()
        print("   -> Usuário 'admin' criado com a senha de ADMIN_PASSWORD.")
    except mysql.connector.Error as err:
        if err.errno == 1062:
            print("   -> Usuário 'admin' já existe.")
        else:
            raise
    finally:
        conn.close()


def main(retries=5, delay=3):
    print("--- SETUP DO BANCO ---")
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            aplicadas = apply_migrations()
            print(f" Migrations aplicadas: {aplicadas or 'nenhuma pendente'}")
            break
        except Exception as e:  # banco ainda subindo no deploy, p.ex.
            last_err = e
            print(f" Tentativa {attempt}/{retries} falhou: {e}")
            if attempt < retries:
                time.sleep(delay)
    else:
        raise RuntimeError(f"Não foi possível aplicar as migrations: {last_err}")

    _seed_admin()
    print(" SUCESSO!")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n ERRO FATAL: {e}", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)
