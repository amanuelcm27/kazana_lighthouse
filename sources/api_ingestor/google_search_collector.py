from core.utils import init_django
init_django()
import json
from openai import OpenAI
from urllib.parse import urlparse
from dotenv import load_dotenv
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
import django
import logging
import os
from bs4 import BeautifulSoup
import re
import requests
from sources.models import RawOpportunity, SourceRegistry
from sources.models import SourceRegistry
from django.utils import timezone


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


def save_to_registry(results, search_term):
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
                search_term=search_term,
                base_url=link,
                active=True,
                last_scraped = timezone.now(),
            )
            logging.info(f"Added: {name} -> {link}")
        else:
            logging.info(f"Exists: {link}")


def refresh_google_queries_task():
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = """
    Generate 24 diverse Google search queries related to:
    - startup funding
    - grants
    - innovation challenges
    - tenders
    - project opportunities
    - equity financing
    - loans
    - venture capital
    
    Make them relevant to Horn of Africa , East Africa or Ethiopian companies , again it must be related to the above mentioned opportunity types.
    Plus make them relevant to current date / time of year.
    Output ONLY a JSON array of 24 strings (no extra text).
    """

    response = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[{"role": "user", "content": prompt}],
    )

    try:
        message = response.choices[0].message
        content = message.content.strip()
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if not match:
            raise ValueError("No JSON array found in GPT response")

        queries = json.loads(match.group())
        print(queries)
        return f"Generated {len(queries)} new queries."
    except Exception as e:
        print(f"Failed to parse GPT response: {e}")
        return "Failed to refresh queries."


def main():
    list_of_queries = ['Ethiopia startup funding opportunities 2025 November', 
                       'East Africa grants for tech startups 2025 call for proposals',
                       'Horn of Africa innovation challenge 2025 Ethiopia',
                       'Ethiopia government tenders 2025 procurement notices', 
                       'East Africa project funding opportunities 2025 December', 
                       'Equity financing for Ethiopian startups 2025 venture capital',
                       'Ethiopia SME loans 2025 government programs', 
                       'East Africa venture capital firms in Ethiopia 2025',
                       'Agritech grants for Ethiopian startups 2025',
                       'UN grants Ethiopia 2025 call for proposals', 
                       'Energy and climate innovation challenge Ethiopia 2025',
                       'Horn of Africa public tenders 2025 Ethiopia Kenya',
                       'Horn of Africa solar energy innovation challenge 2025',
                       'Ethiopia climate finance grants 2025', 
                       'East Africa small business loan programs 2025',
                       'Development project opportunities Ethiopia 2025', 
                       'Equity funding rounds Ethiopia 2025 Q4',
                       'Angel investors East Africa Ethiopia 2025', 
                       'Tech startup grants Ethiopia November 2025',
                       'Public procurement tenders Ethiopia 2025 Q4', 
                       'Grants for women-led startups Ethiopia 2025', 
                       'R&D grants East Africa 2025 Ethiopia', 
                       'Fintech startup funding East Africa 2025',
                       'Ethiopia venture capital funding landscape 2025']
    # print(refresh_google_queries_task())
    for query in list_of_queries:
        results = google_search(query, num_results=10)
        save_to_registry(results , query)
        print(f' saved the follwing links {results}  for query {query} \n')
        logging.info("Source registry updated successfully.")


if __name__ == "__main__":
    main()
