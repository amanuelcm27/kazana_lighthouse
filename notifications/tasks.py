
from celery import shared_task
import logging
from notifications.email_service import send_central_digest
from core.logging import email_logger


@shared_task
def run_email_digest_task():
    send_central_digest()
    email_logger.info("Emails sent")
    return f" Emails sent for this week"