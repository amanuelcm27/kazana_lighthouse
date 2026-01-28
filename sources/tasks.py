from celery import shared_task
from core.logging import scraper_logger, google_logger
from sources.scraper import scrape_google_source
from sources.models import SourceRegistry
from processing.models import CleanedOpportunity
from sources.google_search_collector import google_search, save_to_registry
from datetime import datetime
from django.core.cache import cache
from openai import OpenAI
import json
import os
import re


Max_Pending_Items_in_cleaned_opportunity = 50
Max_unscraped_source_registry_items = 100

def extraction_backlog_high():
    return CleanedOpportunity.objects.filter(status="pending").count() >= Max_Pending_Items_in_cleaned_opportunity

def source_registry_backlog_high():
    return SourceRegistry.objects.filter(active=True, source_type="google", last_scraped__isnull=True).count() >= Max_unscraped_source_registry_items

@shared_task
def run_scraper_task():
    if extraction_backlog_high():
        scraper_logger.warning(
            "Extraction backlog is high. Skipping scraping to prioritize processing."
        )
        return "Skipped scraping due to high extraction backlog."
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
            scraper_logger.error(f"Error scraping {source.base_url}: {e}", exc_info=True)

    return f"Scraped {sources.count()} static sources successfully."


@shared_task
def collect_links_via_google_api_task():
    if source_registry_backlog_high():
        google_logger.warning(
            "SourceRegistry backlog is high. Skipping Google link collection to prioritize scraping."
        )
        return "Skipped Google link collection due to high SourceRegistry backlog."
    queries = cache.get("google_queries_pool")

    if not queries:
        google_logger.warning(
            "No query pool found. Generating queries synchronously.")
        refresh_google_queries_task()  # IMPORTANT: sync call
        queries = cache.get("google_queries_pool") or [
            "latest startup grants and funding opportunities for ethiopian companies and startups"
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
    Generate 6 diverse Google search queries related to:
    - startup funding
    - grants
    - tenders
    - equity financing
    - loans
    - venture capital
    Guidelines:
    - Focus on Horn of Africa, East Africa, with hyper focus for Ethiopia
    - Prefer queries that surface current or recently announced opportunities (ongoing or upcoming)
    Output ONLY a JSON array of 6 strings.
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
        google_logger.error(f"Failed to parse GPT response: {e}" , exc_info=True)
        return "Failed to refresh queries."
