from celery import shared_task
import logging
from matching.matcher import match_startups_to_opportunity
from processing.models import ProcessedOpportunity
# === Logging Setup ===
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

matcher_logger = logging.getLogger("matcher")
matcher_handler = logging.FileHandler("core/logs/matcher.log")
matcher_handler.setFormatter(formatter)
matcher_logger.addHandler(matcher_handler)
matcher_logger.setLevel(logging.INFO)


@shared_task
def run_matching_task():
    
    opportunities = ProcessedOpportunity.objects.all()
    if not opportunities.exists():
        matcher_logger.info("No processed opportunities available for matching.")
        return

    matcher_logger.info(f" Starting matching for {opportunities.count()} processed opportunities.")
    for opp in opportunities:
        match_startups_to_opportunity(opp)

    matcher_logger.info(" Matching process completed.")