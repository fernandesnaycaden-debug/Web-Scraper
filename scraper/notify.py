"""Send the report by email over SMTP."""
import logging
import smtplib
from email.message import EmailMessage

from scraper import config

log = logging.getLogger(__name__)


def send_report(subject, text_body, html_body):
    """Send the report. Returns True on success, False otherwise (never raises)."""
    if not all([config.SMTP_USER, config.SMTP_PASSWORD, config.EMAIL_TO]):
        log.error("Email not sent: set SMTP_USER, SMTP_PASSWORD and EMAIL_TO in .env")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.SMTP_USER
    msg["To"] = config.EMAIL_TO
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        log.error("Email failed: %s", e)
        return False

    log.info("Report emailed to %s", config.EMAIL_TO)
    return True
