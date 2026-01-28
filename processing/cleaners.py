from core.utils import init_django
init_django()

from sources.models import RawOpportunity
from processing.models import CleanedOpportunity
from bs4 import BeautifulSoup
import re
from core.logging import cleaner_logger


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
    )

    if not raw_entries.exists():
        cleaner_logger.info("No pending raw opportunities to process.")
        return
    
    cleaner_logger.info(f"Processing {len(raw_entries)} raw opportunities")

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
        cleaner_logger.info(f"Updated status for: {raw.url}")
    cleaner_logger.info("Processing Raw Opportunities complete.")


if __name__ == "__main__":
    process_raw_opportunities()
