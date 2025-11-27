from core.utils import init_django
init_django()
import os
from openai import OpenAI
import time
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging
from sources.models import RawOpportunity, SourceRegistry


# -------------------- Logging --------------------
logging.basicConfig(
    filename="core/logs/static_scraper.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# -------------------- Config --------------------
MIN_DELAY = 1
MAX_DELAY = 5

COMMON_PATHS = [
    "/about", "/contact", "/privacy", "/terms", "/login", "/signup",
    "/search", "/sitemap", "/feed", "/logout", "/account"
]

IGNORED_TAGS = ["header", "footer", "nav"]

LLM_MODEL = "gpt-5-nano"  # your LLM model
LLM_MAX_LINKS = 30         # max number of links to send per page

# -------------------- Fetch HTML --------------------


def fetch_html(url):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        time.sleep(random.uniform(1, 5))
        return r.text
    except Exception as e:
        logging.error(f"Failed to fetch {url}: {e}")
        return None

# -------------------- Extract Candidate Links --------------------


def extract_candidate_links(base_url, html):
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href:
            continue
        full_url = urljoin(base_url, href)

        if any(full_url.lower().endswith(p) for p in COMMON_PATHS):
            continue
        parent_tags = [parent.name for parent in a.parents]
        if any(tag in parent_tags for tag in IGNORED_TAGS):
            continue
        # store anchor text for context
        anchor_text = a.get_text(strip=True) or urlparse(href).path
        links.add((full_url, anchor_text))

    return list(links)

# -------------------- LLM Evaluation --------------------


def filter_links_with_llm(links):
    if not links:
        return []

    # Limit number of links sent to LLM to reduce tokens
    links = links[:LLM_MAX_LINKS]
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    prompt = """
    
You are an expert funding analyst. From the list of URLs below, identify which ones are likely real **funding opportunities, grants, tenders, or calls for proposals** that a company could apply to. 

**Important:**
- Only consider opportunities related to *funding, grant, equity ,  project, competition, request for proposal , loans , expression of interest, rfp , eoi , or contract opportunity*
- Only output the URLs that are plausible.
- Do not include any explanations, numbers, or extra text.
- Output one URL per line, no commas or bullets.

    """
    for idx, (url, text) in enumerate(links, 1):
        prompt += f"{url} - {text}\n"
    print(f' prompt is :-  {prompt}' )
    try:
        response = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[{"role": "user", "content": prompt}],
        )
        llm_output = response.choices[0].message.content.strip()
        # Extract URLs from LLM response
        filtered_urls = [line.strip() for line in llm_output.splitlines()
                         if line.strip().startswith("http")]
        print(f' llm approved links: {filtered_urls} out of {links}')
        return filtered_urls
    except Exception as e:
        logging.error(f"LLM evaluation failed: {e}")
        return []

# -------------------- Scraper --------------------


def scrape_google_source(source_registry_entry):
    base_url = source_registry_entry.base_url
    domain = urlparse(base_url).netloc

    logging.info(f"Scraping Google-suggested page: {base_url}")
    html = fetch_html(base_url)
    if not html:
        return

    candidate_links = extract_candidate_links(base_url, html)
    filtered_links = filter_links_with_llm(candidate_links)

    for link in filtered_links:
        logging.info(f"Fetching LLM-approved link: {link}")
        page_html = fetch_html(link)
        if page_html:
            try:
                RawOpportunity.objects.create(
                    source_type="google",
                    source_name=domain,
                    url=link,
                    raw_content=page_html
                )
                logging.info(f"Saved RawOpportunity for {link}")

            except Exception as e:
                logging.error(f"Failed to save RawOpportunity for {link}: {e}")

        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


def run_scraper():
    sources = SourceRegistry.objects.filter(active=True, source_type="google").order_by('-id')[:30]
    for source in sources:
        scrape_google_source(source)


if __name__ == "__main__":
    run_scraper()
