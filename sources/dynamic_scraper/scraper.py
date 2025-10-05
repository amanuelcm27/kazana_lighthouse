from core.utils import init_django
init_django()
from sources.models import RawOpportunity, SourceRegistry
import time
import random
import logging
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
import requests
import re



# --- Logging Setup ---
logging.basicConfig(
    filename="core/logs/dynamic_scraper.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

KEYWORDS = ["grant", "funding", "opportunity", "project", "tender", "apply"]

MIN_DELAY = 2
MAX_DELAY = 5

WAIT_TIME = 5  # Seconds to allow JS to render
HEADLESS = True


# --- Selenium Setup Helper ---
def get_driver():
    chrome_options = Options()
    if HEADLESS:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(
        "--disable-blink-features=AutomationControlled")
    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except WebDriverException as e:
        logging.error(f"Failed to initialize Chrome driver: {e}")
        raise


# --- Core Scraping Functions ---
def fetch_dynamic_html(driver, url):
    try:
        driver.get(url)
        time.sleep(WAIT_TIME)
        html = driver.page_source
        time.sleep(random.uniform(0.5, 1.5))
        return html
    except Exception as e:
        logging.error(f"Failed to load {url}: {e}")
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


def scrape_dynamic_source(source_registry_entry, max_depth=2, max_pages=10):
    driver = get_driver()
    base_url = source_registry_entry.base_url
    domain = urlparse(base_url).netloc
    visited = set()
    queue = [(base_url, 0)]

    logging.info(f"Starting dynamic scraping for {domain}")

    try:
        while queue and len(visited) < max_pages:
            url, depth = queue.pop(0)
            if url in visited or depth > max_depth:
                continue

            logging.info(f"Loading {url}")
            html = fetch_dynamic_html(driver, url)
            visited.add(url)

            if html:
                RawOpportunity.objects.create(
                    source_type="dynamic",
                    source_name=domain,
                    url=url,
                    raw_content=html
                )
                logging.info(f"Saved RawOpportunity for {url}")

                if depth < max_depth:
                    candidate_links = extract_candidate_links(base_url, html)
                    for link in candidate_links:
                        if link not in visited and len(visited) < max_pages:
                            queue.append((link, depth + 1))

            # Politeness delay
            time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    except Exception as e:
        logging.error(f"Error scraping source {domain}: {e}")
    finally:
        driver.quit()
        logging.info(f"Closed Selenium driver for {domain}")



def is_dynamic_site(url):
    try:
        html = requests.get(url, timeout=10).text
        soup = BeautifulSoup(html, "html.parser")

        # 1. Check if visible text is almost empty
        visible_text = soup.get_text(strip=True)
        if len(visible_text) < 200:
            return True

        # 2. Check for common JS frameworks (React, Vue, Angular, Next.js, etc.)
        script_tags = " ".join(script.get("src", "") + script.get_text() for script in soup.find_all("script"))
        js_indicators = re.findall(r"(react|vue|angular|next|nuxt|svelte|webpack|bundle|__NEXT_DATA__)", script_tags, re.I)
        if js_indicators:
            return True

        # 3. Check for root div patterns used by SPAs
        if soup.find("div", {"id": re.compile(r"^(app|root|main|__next)$", re.I)}):
            return True

        return False

    except Exception:
        return False


def run_scraper():
    sources = SourceRegistry.objects.filter(active=True)
    for source in sources:
        logging.info(f"Analyzing {source.base_url} to choose scraper...")
        if is_dynamic_site(source.base_url):
            logging.info(f"Using DYNAMIC scraper for {source.base_url}")
            scrape_dynamic_source(source)
        else:
            logging.info(f"Site is Not Dynamic, Skiping {source.base_url}")


if __name__ == "__main__":
    run_scraper()
