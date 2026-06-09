import smtplib
import ssl
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_welcome_email(to_email: str, username: str) -> None:
    mail_server = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    mail_port = int(os.getenv('MAIL_PORT', 587))
    mail_user = os.getenv('MAIL_USERNAME')
    mail_pass = os.getenv('MAIL_PASSWORD')
    mail_from = os.getenv('MAIL_FROM', mail_user)

    if not mail_user or not mail_pass:
        raise RuntimeError("MAIL_USERNAME e MAIL_PASSWORD não configurados no .env")

    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Bem-vindo ao SGG — Sistema de Gestão de Gado'
    msg['From'] = mail_from
    msg['To'] = to_email

    html = f"""
    <html>
    <body style="margin:0;padding:0;background:#EAF3DE;font-family:'DM Sans',sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:40px 16px;">
          <table width="480" cellpadding="0" cellspacing="0"
                 style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(59,109,17,.12);">
            <tr>
              <td style="background:#3B6D11;padding:28px 32px;">
                <p style="margin:0;color:#fff;font-size:20px;font-weight:600;">SGG &mdash; Sistema de Gado</p>
              </td>
            </tr>
            <tr>
              <td style="padding:36px 32px;">
                <h2 style="margin:0 0 8px;color:#1C1C1A;font-size:24px;font-weight:700;">
                  Bem-vindo, {username}! 🐄
                </h2>
                <p style="margin:0 0 24px;color:#4A4A46;font-size:15px;line-height:1.7;">
                  Sua conta no <strong>SGG</strong> foi criada com sucesso.<br>
                  Agora você tem acesso a todas as ferramentas para gerir sua fazenda com eficiência:
                </p>
                <table cellpadding="0" cellspacing="0" style="margin:0 0 28px;width:100%;">
                  <tr>
                    <td style="padding:10px 0;border-bottom:1px solid #F0EDE6;color:#3B6D11;font-size:14px;">
                      ✔ Controle de rebanho e pesagens
                    </td>
                  </tr>
                  <tr>
                    <td style="padding:10px 0;border-bottom:1px solid #F0EDE6;color:#3B6D11;font-size:14px;">
                      ✔ Gestão financeira e fluxo de caixa
                    </td>
                  </tr>
                  <tr>
                    <td style="padding:10px 0;border-bottom:1px solid #F0EDE6;color:#3B6D11;font-size:14px;">
                      ✔ Controle de pastos e lotação
                    </td>
                  </tr>
                  <tr>
                    <td style="padding:10px 0;color:#3B6D11;font-size:14px;">
                      ✔ Estoque de medicamentos e insumos
                    </td>
                  </tr>
                </table>
                <p style="margin:0;color:#888780;font-size:13px;line-height:1.6;">
                  Em caso de dúvidas, responda este email.<br>
                  Bom trabalho na gestão da sua pecuária!
                </p>
              </td>
            </tr>
            <tr>
              <td style="background:#F7F6F2;padding:16px 32px;text-align:center;">
                <p style="margin:0;color:#B0AEA6;font-size:12px;">SGG — Sistema de Gestão de Gado</p>
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """

    msg.attach(MIMEText(html, 'html'))

    context = ssl.create_default_context()
    with smtplib.SMTP(mail_server, mail_port) as server:
        server.ehlo()
        server.starttls(context=context)
        server.login(mail_user, mail_pass)
        server.sendmail(mail_from, to_email, msg.as_string())


def send_reset_code(to_email: str, code: str) -> None:
    mail_server = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    mail_port = int(os.getenv('MAIL_PORT', 587))
    mail_user = os.getenv('MAIL_USERNAME')
    mail_pass = os.getenv('MAIL_PASSWORD')
    mail_from = os.getenv('MAIL_FROM', mail_user)

    if not mail_user or not mail_pass:
        raise RuntimeError("MAIL_USERNAME e MAIL_PASSWORD não configurados no .env")

    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Código de Verificação — SGG Sistema de Gado'
    msg['From'] = mail_from
    msg['To'] = to_email

    html = f"""
    <html>
    <body style="margin:0;padding:0;background:#EAF3DE;font-family:'DM Sans',sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:40px 16px;">
          <table width="400" cellpadding="0" cellspacing="0"
                 style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(59,109,17,.12);">
            <tr>
              <td style="background:#3B6D11;padding:24px 32px;">
                <p style="margin:0;color:#fff;font-size:20px;font-weight:600;">SGG &mdash; Sistema de Gado</p>
              </td>
            </tr>
            <tr>
              <td style="padding:32px;">
                <h2 style="margin:0 0 12px;color:#1C1C1A;font-size:22px;">Recuperação de Senha</h2>
                <p style="margin:0 0 24px;color:#4A4A46;font-size:15px;line-height:1.6;">
                  Use o código abaixo para redefinir sua senha.<br>
                  Ele expira em <strong>15 minutos</strong>.
                </p>
                <div style="text-align:center;margin:0 0 28px;">
                  <span style="display:inline-block;font-size:42px;font-weight:700;letter-spacing:12px;
                               color:#3B6D11;background:#EAF3DE;padding:18px 28px;border-radius:10px;
                               border:2px solid #C0DD97;">
                    {code}
                  </span>
                </div>
                <p style="margin:0;color:#888780;font-size:13px;line-height:1.5;">
                  Se você não solicitou este código, ignore este email.<br>
                  Sua senha permanece inalterada.
                </p>
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """

    msg.attach(MIMEText(html, 'html'))

    context = ssl.create_default_context()
    with smtplib.SMTP(mail_server, mail_port) as server:
        server.ehlo()
        server.starttls(context=context)
        server.login(mail_user, mail_pass)
        server.sendmail(mail_from, to_email, msg.as_string())
