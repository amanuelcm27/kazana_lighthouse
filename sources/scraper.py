from core.utils import init_django
init_django()
import os
from openai import OpenAI
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from sources.models import RawOpportunity, SourceRegistry
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from django.utils import timezone
from core.logging import scraper_logger


# -------------------- Config --------------------
MIN_DELAY = 1
MAX_DELAY = 5

COMMON_PATHS = [
    "/about", "/contact", "/privacy", "/terms", "/login", "/signup",
    "/search", "/sitemap", "/feed", "/logout", "/account" , "/faqs"
]
BLOCKED_EXTENSIONS = (
    ".pdf", ".doc", ".docx",
    ".xls", ".xlsx",
    ".ppt", ".pptx",
    ".zip", ".rar", ".7z",
    ".csv", ".json",
    ".jpg", ".jpeg", ".png", ".gif", ".svg",
)

IGNORED_TAGS = ["header", "footer", "nav"]

LLM_MODEL = "gpt-5-mini"  
LLM_MAX_LINKS = 30         

# -------------------- Fetch HTML --------------------


def fetch_html(url):
    parsed = urlparse(url)
    if parsed.path.lower().endswith(BLOCKED_EXTENSIONS):
        scraper_logger.info(f"Skipping file URL (not HTML): {url}")
        return None
    
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
                scraper_logger.warning(f"Timeout reached for {url}, extracting partial content")

            html = page.content()
            browser.close()
            return html

    except Exception as e:
        scraper_logger.error(f"Playwright failed to fetch {url}: {e}", exc_info=True)
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
        parsed = urlparse(full_url)
        path = parsed.path.lower()

        # skip files (PDFs, docs, zips, images, etc.)
        if path.endswith(BLOCKED_EXTENSIONS):
            continue

        # skip common non-opportunity pages
        if any(path.endswith(p) for p in COMMON_PATHS):
            continue

        # skip nav/header/footer links
        parent_tags = [parent.name for parent in a.parents]
        if any(tag in parent_tags for tag in IGNORED_TAGS):
            continue

        anchor_text = a.get_text(strip=True) or path
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
        - Only consider opportunities links related to funding, grant, equity financing, competition, request for proposal , loans , expression of interest, rfp , eoi , or contract opportunities
        - Do not consider any links that are files like pdfs or docs or any other non-html resources.
        - Do not include any explanations, numbers, or extra text.
        - Output one URL per line, no commas or bullets.

    """
    for idx, (url, text) in enumerate(links, 1):
        prompt += f"{url} - {text}\n"
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
        scraper_logger.error(f"LLM evaluation failed: {e}", exc_info=True)
        return []

# -------------------- Scraper --------------------

def scrape_google_source(source_registry_entry):
    base_url = source_registry_entry.base_url
    domain = urlparse(base_url).netloc

    scraper_logger.info(f"Scraping Google-suggested page: {base_url}")
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
        scraper_logger.error(f"Failed to save BaseURL RawOpportunity for {base_url}: {e}", exc_info=True)
        
    candidate_links = extract_candidate_links(base_url, html)
    scraper_logger.info(f"Extracted {len(candidate_links)} candidate links from {base_url}")
    filtered_links = filter_links_with_llm(candidate_links)
    saved_links_count = 0
    for link in filtered_links:
        scraper_logger.info(f"Fetching LLM-approved link: {link}")
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
                scraper_logger.info(f"Saved RawOpportunity for {link}")
                saved_links_count += 1
            except Exception as e:
                scraper_logger.error(f"Failed to save RawOpportunity for {link}: {e}", exc_info=True)

    scraper_logger.info(f"Scraping complete for {base_url}. Saved {saved_links_count} opportunities.")

def run_scraper():
    sources = SourceRegistry.objects.filter(active=True, source_type="google", last_scraped__isnull=True).order_by('-id')[:50]
    for source in sources:
        scrape_google_source(source)

if __name__ == "__main__":
    run_scraper()
