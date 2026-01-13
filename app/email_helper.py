import logging
from .models import SystemSetting

logger = logging.getLogger(__name__)

def send_email(to_addr, subject, body):
    provider = SystemSetting.get_value('EMAIL_PROVIDER', 'smtp')
    from_addr = SystemSetting.get_value('EMAIL_FROM')
    
    try:
        if provider == 'sendgrid':
             api_key = SystemSetting.get_value('SENDGRID_API_KEY')
             if api_key and from_addr:
                from sendgrid import SendGridAPIClient
                from sendgrid.helpers.mail import Mail
                message = Mail(from_email=from_addr, to_emails=to_addr, subject=subject, plain_text_content=body)
                sg = SendGridAPIClient(api_key)
                sg.send(message)
        else:
            # SMTP
            host = SystemSetting.get_value('EMAIL_HOST')
            port = SystemSetting.get_value('EMAIL_PORT')
            user_email = SystemSetting.get_value('EMAIL_USER')
            password = SystemSetting.get_value('EMAIL_PASSWORD')
            
            if host and port and user_email and password:
                import smtplib
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart
                
                email_msg = MIMEMultipart()
                email_msg['From'] = from_addr or user_email
                email_msg['To'] = to_addr
                email_msg['Subject'] = subject
                email_msg.attach(MIMEText(body, 'plain'))
                
                server = smtplib.SMTP(host, int(port))
                server.starttls()
                server.login(user_email, password)
                server.send_message(email_msg)
                server.quit()
    except Exception as e:
        logger.error(f"Email failed: {e}")
