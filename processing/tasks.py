from celery import shared_task
import logging
from processing.cleaners import process_raw_opportunities
from processing.models import CleanedOpportunity
from processing.llm_extractor import extract_opportunity_data
from core.logging import cleaner_logger, llm_extractor_logger
    
    
# === Tasks ===
@shared_task
def run_cleaning_task():
    process_raw_opportunities()
    cleaner_logger.info("Cleaning complete")
    return "Cleaning Complete"

@shared_task
def run_llm_extraction_task():
    pending_items = CleanedOpportunity.objects.filter(status="pending").order_by('-id')[:15]
    if not pending_items.exists():
        llm_extractor_logger.info("No pending items to process.")
        return

    llm_extractor_logger.info(f"Starting extraction for {pending_items.count()} pending items...")
    for item in pending_items:
        llm_extractor_logger.info(f"Extracting began for {item.source_name}")
        extract_opportunity_data(item)
    llm_extractor_logger.info("Extraction batch completed.")
    return f"LLM extraction Complete for {pending_items.count()}"
