from celery import shared_task
import logging
from sources.static_scraper.scraper import scrape_static_source
from sources.models import SourceRegistry
from sources.dynamic_scraper.scraper import scrape_dynamic_source, is_dynamic_site
from sources.api_ingestor.google_search_collector import google_search, save_to_registry
from datetime import datetime
from django.core.cache import cache
from openai import OpenAI
import json
import os
import re


static_logger = logging.getLogger("static_scraper")
dynamic_logger = logging.getLogger("dynamic_scraper")
google_logger = logging.getLogger("google_ingestor")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# File handlers (optional but recommended)
static_handler = logging.FileHandler("core/logs/static_scraper.log")
dynamic_handler = logging.FileHandler("core/logs/dynamic_scraper.log")
google_handler = logging.FileHandler("core/logs/google_ingestor.log")

for handler, log in [
    (static_handler, static_logger),
    (dynamic_handler, dynamic_logger),
    (google_handler, google_logger),
]:
    log.addHandler(handler)


@shared_task
def run_static_scraper_task():
    sources = SourceRegistry.objects.filter(active=True, source_type="google")
    if not sources.exists():
        static_logger.warning("No active static sources found.")
        return "No sources to scrape."

    static_logger.info(f"Found {sources.count()} static sources to scrape.")

    for source in sources:
        try:
            static_logger.info(f"Scraping source: {source.base_url}")
            scrape_static_source(source)
        except Exception as e:
            static_logger.error(f"Error scraping {source.base_url}: {e}")

    return f"Scraped {sources.count()} static sources successfully."


@shared_task
def run_dynamic_scraper_task():
    sources = SourceRegistry.objects.filter(active=True)
    if not sources.exists():
        static_logger.warning("No active sources found.")
        return "No sources to scrape."
    
    for source in sources:
        dynamic_logger.info(
            f"Analyzing {source.base_url} to choose scraper...")
        if is_dynamic_site(source.base_url):
            dynamic_logger.info(f"Using DYNAMIC scraper for {source.base_url}")
            scrape_dynamic_source(source)
        else:
            dynamic_logger.info(
                f"Site is Not Dynamic, Skiping {source.base_url}")

    return f"Dynamic scraper task completed for {sources.count()} sources."


@shared_task
def collect_links_via_google_api_task():

    queries = cache.get("google_queries_pool", [])
    if not queries:
        google_logger.warning("No query pool found. Generating fallback query.")
        refresh_google_queries_task.delay()  # refresh queries initially ...
        queries = ["latest startup grants and funding opportunities 2025"]

    # Use round-robin selection
    index = cache.get("google_query_index", 0)
    query = queries[index % len(queries)]
    cache.set("google_query_index", (index + 1) %
              len(queries), timeout=60 * 60 * 24)

    results = google_search(query, num_results=10)
    save_to_registry(results , query)
    google_logger.info(
        f"Used query '{query}' → collected {len(results)} links.")
    return f"Collected {len(results)} links from query '{query}'."


@shared_task
def refresh_google_queries_task():
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = """
    Generate 24 diverse Google search queries related to:
    - startup funding
    - grants
    - innovation challenges
    - tenders
    - project opportunities
    Make them globally relevant and any sector or funding type.
    Output ONLY a JSON array of 24 strings (no extra text).
    """

    response = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[{"role": "user", "content": prompt}],
    )

    try:
        message = response.choices[0].message
        print(f'gpt response {message}')
        content = message.content.strip()
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if not match:
            raise ValueError("No JSON array found in GPT response")

        queries = json.loads(match.group())
        cache.set("google_queries_pool", queries,
                  timeout=60 * 60 * 6)  # 6 hours
        return f"Generated {len(queries)} new queries."
    except Exception as e:
        google_logger.error(f"Failed to parse GPT response: {e}")
        return "Failed to refresh queries."
