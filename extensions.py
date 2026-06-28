from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from apscheduler.schedulers.background import BackgroundScheduler
from flask_compress import Compress

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    default_limits=[],
)

scheduler = BackgroundScheduler(timezone='America/Sao_Paulo')
compress = Compress()
