from celery import shared_task
import logging
from matching.matcher import match_startups_to_opportunity
from processing.models import ProcessedOpportunity
from core.logging import matcher_logger

@shared_task
def run_matching_task():
    opp_batch = 30  # cap per run
    opportunities = ProcessedOpportunity.objects.filter(matching_status="pending").order_by('-created_at')[:opp_batch]

    if not opportunities.exists():
        matcher_logger.info("No pending opportunities for matching.")
        return

    matcher_logger.info(f"Starting matching for {opportunities.count()} pending opportunities.")
    for opp in opportunities:
        match_startups_to_opportunity(opp)
    matcher_logger.info("Matching process completed.")
