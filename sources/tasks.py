from celery import shared_task
import time

@shared_task
def test_task(name="World"):
    time.sleep(2)
    return f"Hello {name}! Task executed successfully 🚀"
