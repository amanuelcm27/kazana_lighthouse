import time
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging
from core.utils import init_django
init_django()

from sources.models import RawOpportunity, SourceRegistry

logging.basicConfig(
    filename="core/logs/static_scraper.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

KEYWORDS = ["grant", "funding", "opportunity", "procurement", "tender", "opportunity"]

MIN_DELAY = 1
MAX_DELAY = 5

def fetch_html(url):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        time.sleep(random.uniform(0.5, 1.5))
        return r.text
    except Exception as e:
        logging.error(f"Failed to fetch {url}: {e}")
        return None

def extract_candidate_links(base_url, html):
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full_url = urljoin(base_url, href)
        if any(k in href.lower() for k in KEYWORDS):
            links.add(full_url)
    return links

def scrape_static_source(source_registry_entry, max_depth=2, max_pages=10):
    base_url = source_registry_entry.base_url
    domain = urlparse(base_url).netloc
    visited = set()
    queue = [(base_url, 0)]

    while queue and len(visited) < max_pages:
        url, depth = queue.pop(0)
        if url in visited or depth > max_depth:
            continue

        logging.info(f"Fetching {url}")
        html = fetch_html(url)
        visited.add(url)

        if html:
            # Save raw content
            RawOpportunity.objects.create(
                source_type="static",
                source_name=domain,
                url=url,
                raw_content=html
            )
            logging.info(f"Saved RawOpportunity for {url}")

            # Extract candidate links for further crawling
            if depth < max_depth:
                candidate_links = extract_candidate_links(base_url, html)
                for link in candidate_links:
                    if link not in visited and len(visited) < max_pages:
                        queue.append((link, depth + 1))

        # Politeness delay between requests
        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

def run_scraper():
    sources = SourceRegistry.objects.filter(active=True, source_type="google")
    for source in sources:
        logging.info(f"Starting scraping for {source.base_url}")
        scrape_static_source(source)

if __name__ == "__main__":
    run_scraper()
