from core.utils import init_django
init_django()

from sources.models import RawOpportunity
from processing.models import CleanedOpportunity
from bs4 import BeautifulSoup
import logging
import re

logging.basicConfig(
    filename="core/logs/cleaners.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def clean_html(html_content):
    """Extract visible text from raw HTML and remove scripts/styles."""
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove <script> and <style> tags
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()

    # Get visible text
    text = soup.get_text(separator="\n")

    # Clean excessive whitespace and line breaks
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'\s+', ' ', text).strip()

    return text

def process_raw_opportunities(batch_size=50):
    raw_entries = RawOpportunity.objects.filter(
        status="pending"
    )[:batch_size]

    logging.info(f"Processing {len(raw_entries)} raw opportunities")

    for raw in raw_entries:
        cleaned_text = clean_html(raw.raw_content)
        if cleaned_text: 
            CleanedOpportunity.objects.create(
                raw_opportunity=raw,
                source_name=raw.source_name,
                url=raw.url,
                cleaned_content=cleaned_text
            )
            raw.status = "cleaned"

        raw.save()
        logging.info(f"Updated status for: {raw.url}")
    logging.info("Processing Raw Opportunities complete.")


if __name__ == "__main__":
    process_raw_opportunities()
