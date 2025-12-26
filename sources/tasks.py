from celery import shared_task
import logging
from sources.scraper import scrape_google_source
from sources.models import SourceRegistry
from sources.google_search_collector import google_search, save_to_registry
from datetime import datetime
from django.core.cache import cache
from openai import OpenAI
import json
import os
import re


scraper_logger = logging.getLogger("scraper_logger")
google_logger = logging.getLogger("google_logger")

formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)

scraper_handler = logging.FileHandler("core/logs/scraper_logger.log")
scraper_handler.setFormatter(formatter)

google_handler = logging.FileHandler("core/logs/google_ingestor.log")
google_handler.setFormatter(formatter)


for handler, log in [
    (scraper_handler, scraper_logger),
    (google_handler, google_logger),
]:
    if not log.handlers:
        log.addHandler(handler)
    log.setLevel(logging.INFO)


@shared_task
def run_scraper_task():
    sources = SourceRegistry.objects.filter(
        active=True, source_type="google", last_scraped__isnull=True).order_by('-id')[:40]
    if not sources.exists():
        scraper_logger.warning("No active static sources found.")
        return "No sources to scrape."

    scraper_logger.info(f"Found {sources.count()} static sources to scrape.")

    for source in sources:
        try:
            scraper_logger.info(f"Scraping source: {source.base_url}")
            scrape_google_source(source)
        except Exception as e:
            scraper_logger.error(f"Error scraping {source.base_url}: {e}")

    return f"Scraped {sources.count()} static sources successfully."


@shared_task
def collect_links_via_google_api_task():
    queries = cache.get("google_queries_pool")

    if not queries:
        google_logger.warning(
            "No query pool found. Generating queries synchronously.")
        refresh_google_queries_task()  # IMPORTANT: sync call
        queries = cache.get("google_queries_pool") or [
            "latest startup grants and funding opportunities 2025"
        ]

    index = cache.get("google_query_index", 0)
    query = queries[index % len(queries)]
    google_logger.info(f"Using query index {index}: {query}")
    cache.set(
        "google_query_index",
        (index + 1) % len(queries),
        timeout=60 * 60 * 24
    )

    results = google_search(query, num_results=10)
    google_logger.info(f"Collected {len(results)}")
    save_to_registry(results, query)

    google_logger.info(
        f"Used query '{query}' → collected {len(results)} links."
    )
    return f"Collected {len(results)} links using query '{query}'."


@shared_task
def refresh_google_queries_task():
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = """
    Generate 8 diverse Google search queries related to:

    - startup funding
    - grants
    - tenders
    - project opportunities
    - equity financing
    - loans
    - venture capital

    Guidelines:
    - Focus on Horn of Africa, East Africa, with preference for Ethiopia
    - Prefer queries that surface:
        - NGO announcements
        - Development organizations
        - Public tenders
        - Investment programs
    - Include queries that may surface:
        - LinkedIn posts
        - Social media Posts 
        - Consulting or procurement notices
    - Prefer queries that surface current or recently announced opportunities (ongoing or upcoming)


    Output ONLY a JSON array of 10 strings.

    
    """

    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[{"role": "user", "content": prompt}],
    )

    try:
        message = response.choices[0].message
        content = message.content.strip()
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if not match:
            raise ValueError("No JSON array found in GPT response")
        queries = json.loads(match.group())
        cache.set("google_queries_pool", queries,
                  timeout=60 * 60 * 24)
        cache.set("google_query_index", 0, timeout=60 * 60 * 24)
        google_logger.info(f"Refreshed Google queries pool with {len(queries)} queries.")
        return f"Generated {len(queries)} new queries."
    except Exception as e:
        google_logger.error(f"Failed to parse GPT response: {e}")
        return "Failed to refresh queries."
