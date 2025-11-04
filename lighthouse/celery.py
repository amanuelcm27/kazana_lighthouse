from __future__ import absolute_import, unicode_literals
import os
import sources.tasks
from celery import Celery
from celery.schedules import crontab


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lighthouse.settings")

app = Celery("lighthouse")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()





