from celery import shared_task
import logging
from processing.cleaners import process_raw_opportunities
from processing.models import CleanedOpportunity
from processing.llm_extractor import extract_opportunity_data

formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
cleaner_logger = logging.getLogger("cleaners")
llm_extractor_logger = logging.getLogger("llm_extractor")

cleaner_handler = logging.FileHandler("core/logs/cleaners.log")
cleaner_handler.setFormatter(formatter)


llm_extractor_handler = logging.FileHandler("core/logs/llm_extractor.log")
llm_extractor_handler.setFormatter(formatter)


for handler, log in [
    (cleaner_handler, cleaner_logger),
    (llm_extractor_handler, llm_extractor_logger),
]:
    if not log.handlers:
        log.addHandler(handler)
    log.setLevel(logging.INFO)
    
    
# === Tasks ===
@shared_task
def run_cleaning_task():
    process_raw_opportunities()
    cleaner_logger.info("Cleaning complete")
    return "Cleaning Complete"

@shared_task
def run_llm_extraction_task():
    pending_items = CleanedOpportunity.objects.filter(status="pending").order_by('-id')[:30]
    if not pending_items.exists():
        llm_extractor_logger.info("No pending items to process.")
        return

    llm_extractor_logger.info(f"Starting extraction for {pending_items.count()} pending items...")
    for item in pending_items:
        extract_opportunity_data(item)
    llm_extractor_logger.info("Extraction batch completed.")
    return f"LLM extraction Complete for {pending_items.count()}"
