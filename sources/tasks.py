from celery import shared_task
import logging
from sources.static_scraper.scraper import scrape_static_source
from sources.models import SourceRegistry

logger = logging.getLogger(__name__)

@shared_task
def run_static_scraper_task():
    sources = SourceRegistry.objects.filter(active=True, source_type="google")
    if not sources.exists():
        logger.warning("No active static sources found.")
        return "No sources to scrape."

    logger.info(f"Found {sources.count()} static sources to scrape.")

    for source in sources:
        try:
            logger.info(f"Scraping source: {source.base_url}")
            scrape_static_source(source)
        except Exception as e:
            logger.error(f"Error scraping {source.base_url}: {e}")

    return f"Scraped {sources.count()} static sources successfully."

