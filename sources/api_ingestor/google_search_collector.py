import requests
import re
from bs4 import BeautifulSoup
import os
import logging
import django
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
from urllib.parse import urlparse
from core.utils import init_django
init_django()

from sources.models import RawOpportunity, SourceRegistry


from sources.models import SourceRegistry

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SEARCH_ENGINE_ID = os.getenv("GOOGLE_CX")

logging.basicConfig(
    filename="core/logs/google_ingestor.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def normalize_url(url):
    """Remove fragments and ensure https."""
    parsed = urlparse(url)
    base = f"{parsed.scheme or 'https'}://{parsed.netloc}{parsed.path}"
    return base.rstrip('/')


def google_search(query, num_results=10):
    """Query Google Custom Search API safely."""
    try:
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        res = service.cse().list(q=query, cx=SEARCH_ENGINE_ID, num=num_results).execute()
        return res.get("items", [])
    except HttpError as e:
        logging.error(f"Google API error: {e}")
        return []


def save_to_registry(results , search_term):
    """Insert into DB if new."""
    for item in results:
        link = normalize_url(item.get("link", ""))
        if not link:
            continue
        name = urlparse(link).netloc
        if not SourceRegistry.objects.filter(base_url=link).exists():
            SourceRegistry.objects.create(
                name=name,
                source_type="google",
                search_term = search_term,
                base_url=link,
                active=True
            )
            logging.info(f"Added: {name} -> {link}")
        else:
            logging.info(f"Exists: {link}")


def main():
    query = "Startup grants, funding opportunities, projects, expressions of interest for startups"
    results = google_search(query, num_results=10)
    save_to_registry(results , query)
    logging.info("Source registry updated successfully.")


if __name__ == "__main__":
    main()
