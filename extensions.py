import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from apscheduler.schedulers.background import BackgroundScheduler
from flask_compress import Compress

# Em produção com múltiplos workers Gunicorn, usar Redis para compartilhar contadores.
# Sem REDIS_URL, cai para memória por worker (aceitável em dev, inseguro em prod).
_REDIS_URL = os.getenv('REDIS_URL')
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_REDIS_URL if _REDIS_URL else "memory://",
    default_limits=[],
)

scheduler = BackgroundScheduler(timezone='America/Sao_Paulo')
compress = Compress()
