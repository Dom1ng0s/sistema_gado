import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = 3
timeout = 60
preload_app = True


def post_fork(server, worker):
    """Recria o pool do Postgres em cada worker após o fork — sockets herdados do
    master não podem ser compartilhados entre processos.

    Desativa o scheduler em workers filhos (age > 1). Com preload_app=True o scheduler
    inicia no master antes do fork; threads não sobrevivem ao fork, mas o guard evita
    restart acidental em workers quando preload_app for False.
    """
    import db_config
    db_config.reset_pool()

    # Apenas o primeiro worker pode iniciar o scheduler (age=1 é o worker inicial)
    if worker.age > 1:
        os.environ['SCHEDULER_ENABLED'] = 'false'
