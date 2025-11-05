
from celery import shared_task
import logging
from notifications.email_service import send_central_digest
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

email_logger = logging.getLogger("email_service")
email_handler = logging.FileHandler("core/logs/email_service.log")
email_handler.setFormatter(formatter)
email_logger.addHandler(email_handler)
email_logger.setLevel(logging.INFO)



@shared_task
def run_email_digest_task():
    send_central_digest()
    email_logger.info("Emails sent")
    return f" Emails sent for this week"