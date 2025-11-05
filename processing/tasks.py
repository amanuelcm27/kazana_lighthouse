from celery import shared_task
import logging
from processing.cleaners import process_raw_opportunities
from processing.models import CleanedOpportunity
from processing.llm_extractor import extract_opportunity_data

# === Logging Setup ===
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

cleaner_logger = logging.getLogger("cleaners")
cleaner_handler = logging.FileHandler("core/logs/cleaners.log")
cleaner_handler.setFormatter(formatter)
cleaner_logger.addHandler(cleaner_handler)
cleaner_logger.setLevel(logging.INFO)

llm_extractor_logger = logging.getLogger("llm_extractor")
llm_extractor_handler = logging.FileHandler("core/logs/llm_extractor.log")
llm_extractor_handler.setFormatter(formatter)
llm_extractor_logger.addHandler(llm_extractor_handler)
llm_extractor_logger.setLevel(logging.INFO)

# === Tasks ===
@shared_task
def run_cleaning_task():
    process_raw_opportunities()
    cleaner_logger.info("Cleaning complete")
    return "Cleaning Complete"

@shared_task
def run_llm_extraction_task():
    pending_items = CleanedOpportunity.objects.filter(status="pending")[:6]
    if not pending_items.exists():
        llm_extractor_logger.info("No pending items to process.")
        return

    llm_extractor_logger.info(f"Starting extraction for {pending_items.count()} pending items...")
    for item in pending_items:
        extract_opportunity_data(item)
    llm_extractor_logger.info("Extraction batch completed.")
    return f"LLM extraction Complete for {pending_items.count()}"
