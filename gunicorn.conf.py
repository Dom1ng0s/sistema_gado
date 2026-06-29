import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = 3
timeout = 60
preload_app = True


def post_fork(server, worker):
    """Reinitializa o pool MySQL em cada worker após fork — evita compartilhar sockets.

    Desativa o scheduler em workers filhos (age > 1). Com preload_app=True o scheduler
    inicia no master antes do fork; threads não sobrevivem ao fork, mas o guard evita
    restart acidental em workers quando preload_app for False.
    """
    import db_config
    try:
        import mysql.connector.pooling
        db_config.connection_pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name="gado_pool",
            pool_size=5,
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME'),
            port=int(os.getenv('DB_PORT', 3306)),
            autocommit=False,
            connection_timeout=10,
        )
    except Exception:
        db_config.connection_pool = None

    # Apenas o primeiro worker pode iniciar o scheduler (age=1 é o worker inicial)
    if worker.age > 1:
        os.environ['SCHEDULER_ENABLED'] = 'false'
