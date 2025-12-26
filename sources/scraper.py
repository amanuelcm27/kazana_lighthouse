from core.utils import init_django
init_django()
import os
from openai import OpenAI
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging
from sources.models import RawOpportunity, SourceRegistry
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from django.utils import timezone


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

LLM_MODEL = "gpt-5-mini"  
LLM_MAX_LINKS = 30         

# -------------------- Fetch HTML --------------------


def fetch_html(url):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                java_script_enabled=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            )
            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=23000)
            except PlaywrightTimeoutError:
                logging.warning(f"Timeout reached for {url}, extracting partial content")

            html = page.content()
            browser.close()
            return html

    except Exception as e:
        logging.error(f"Playwright failed to fetch {url}: {e}")
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
        - Only consider opportunities related to *funding, grant, equity financing ,  project, competition, request for proposal , loans , expression of interest, rfp , eoi , or contract opportunity*
        - Links from development banks, NGOs, governments, linkedin or recognized organizations should be prioritized.
        - Do not include any explanations, numbers, or extra text.
        - Output one URL per line, no commas or bullets.

    """
    for idx, (url, text) in enumerate(links, 1):
        prompt += f"{url} - {text}\n"
    print(f' prompt is :-  {prompt}' )
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
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
    # save base page as RawOpportunity
    try:
        RawOpportunity.objects.create(
            source_type="google",
            source_name=domain,
            url=base_url,
            raw_content=html
        )
        source_registry_entry.last_scraped = timezone.now()
        source_registry_entry.save()
    except Exception as e:
        logging.error(f"Failed to save BaseURL RawOpportunity for {base_url}: {e}")
        
    candidate_links = extract_candidate_links(base_url, html)
    logging.info(f"Extracted {len(candidate_links)} candidate links from {base_url}")
    filtered_links = filter_links_with_llm(candidate_links)
    saved_links_count = 0
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
                source_registry_entry.last_scraped = timezone.now()
                source_registry_entry.save()
                logging.info(f"Saved RawOpportunity for {link}")
                saved_links_count += 1
            except Exception as e:
                logging.error(f"Failed to save RawOpportunity for {link}: {e}")

    logging.info(f"Scraping complete for {base_url}. Saved {saved_links_count} opportunities.")

def run_scraper():
    sources = SourceRegistry.objects.filter(active=True, source_type="google", last_scraped__isnull=True).order_by('-id')[:50]
    for source in sources:
        scrape_google_source(source)

if __name__ == "__main__":
    run_scraper()
