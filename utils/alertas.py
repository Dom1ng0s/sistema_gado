import logging
from collections import defaultdict
from db_config import get_db_cursor

logger = logging.getLogger(__name__)


def _agrupar_por_usuario(rows):
    """rows: [(user_id, email, *dados)] -> [(email, [dados, ...]), ...] preservando ordem.

    Agrupa por user_id (não por email) — email não tem UNIQUE constraint em
    usuarios, então duas contas poderiam compartilhar o mesmo endereço.
    """
    dados_por_uid = defaultdict(list)
    email_por_uid = {}
    ordem_uids = []
    for user_id, email, *dados in rows:
        if user_id not in email_por_uid:
            ordem_uids.append(user_id)
        email_por_uid[user_id] = email
        dados_por_uid[user_id].append(tuple(dados))
    return [(email_por_uid[uid], dados_por_uid[uid]) for uid in ordem_uids]


def verificar_contas_vencendo(app):
    with app.app_context():
        try:
            from utils.email_service import send_alert_contas
            with get_db_cursor() as cursor:
                cursor.execute(
                    "SELECT fs.user_id, u.email, fs.descricao, fs.valor, fs.vencimento "
                    "FROM financial_schedule fs "
                    "JOIN usuarios u ON u.id = fs.user_id "
                    "WHERE fs.status = 'pendente' AND fs.deleted_at IS NULL "
                    "AND fs.vencimento <= DATE_ADD(CURDATE(), INTERVAL 3 DAY) "
                    "AND u.email IS NOT NULL AND u.email != '' "
                    "ORDER BY fs.user_id, fs.vencimento ASC"
                )
                rows = cursor.fetchall()
            for email, contas in _agrupar_por_usuario(rows):
                send_alert_contas(email, contas)
        except Exception as e:
            logger.error(f"Alerta contas: {e}", exc_info=True)


def verificar_protocolos_vencendo(app):
    with app.app_context():
        try:
            from utils.email_service import send_alert_protocolo
            with get_db_cursor() as cursor:
                cursor.execute(
                    "SELECT ps.user_id, u.email, ps.nome, ps.proxima_aplicacao "
                    "FROM protocolos_sanitarios ps "
                    "JOIN usuarios u ON u.id = ps.user_id "
                    "WHERE ps.ativo = 1 "
                    "AND ps.proxima_aplicacao <= DATE_ADD(CURDATE(), INTERVAL 7 DAY) "
                    "AND u.email IS NOT NULL AND u.email != '' "
                    "ORDER BY ps.user_id, ps.proxima_aplicacao ASC"
                )
                rows = cursor.fetchall()
            for email, protocolos in _agrupar_por_usuario(rows):
                send_alert_protocolo(email, protocolos)
        except Exception as e:
            logger.error(f"Alerta protocolos: {e}", exc_info=True)


def verificar_feedback_7dias(app):
    with app.app_context():
        try:
            from utils.email_service import send_feedback_request
            with get_db_cursor() as cursor:
                cursor.execute(
                    "SELECT username, email FROM usuarios "
                    "WHERE email IS NOT NULL AND email != '' "
                    "AND DATE(created_at) = DATE_SUB(CURDATE(), INTERVAL 7 DAY)"
                )
                usuarios = cursor.fetchall()
            for username, email in usuarios:
                send_feedback_request(email, username)
                logger.info(f"Feedback solicitado: {username}")
        except Exception as e:
            logger.error(f"Alerta feedback: {e}", exc_info=True)


def verificar_estoque_critico(app):
    with app.app_context():
        try:
            from utils.email_service import send_alert_estoque
            with get_db_cursor() as cursor:
                cursor.execute(
                    "SELECT v.user_id, u.email, v.nome, v.saldo_atual, v.unidade, "
                    "  v.proxima_validade, v.tem_vencido "
                    "FROM vw_saldo_estoque v "
                    "JOIN usuarios u ON u.id = v.user_id "
                    "WHERE (v.abaixo_minimo = 1 OR v.tem_vencido = 1) "
                    "AND u.email IS NOT NULL AND u.email != '' "
                    "ORDER BY v.user_id"
                )
                rows = cursor.fetchall()
            for email, produtos in _agrupar_por_usuario(rows):
                send_alert_estoque(email, produtos)
        except Exception as e:
            logger.error(f"Alerta estoque: {e}", exc_info=True)
