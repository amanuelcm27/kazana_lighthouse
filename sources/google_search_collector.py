from core.utils import init_django
init_django()

from django.utils import timezone
from sources.models import SourceRegistry
from sources.models import RawOpportunity, SourceRegistry
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
from openai import OpenAI
import json


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
            )
            logging.info(f"Added: {name} -> {link}")
        else:
            logging.info(f"Exists: {link}")


def refresh_google_queries_task():
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = """
    Generate 10 diverse Google search queries related to:
    
    - startup funding
    - grants
    - tenders
    - project opportunities
    - equity financing
    - loans
    - venture capital
    
    Make them relevant to Horn of Africa , East Africa or specifically prefered if its Ethiopia focused , again it must be related to the above mentioned opportunity types.
    Plus make them relevant to current date or time of year.
    Output ONLY a JSON array of 10 strings (no extra text).
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
    list_of_queries = ['Ethiopia startup funding 2025 grants December opportunities', 
                       'Ethiopia government grants for startups 2025 December',
                       'East Africa tenders 2025 Ethiopia procurement December',
                       'Ethiopia project opportunities 2025 grants for startups', 
                       'Ethiopia venture capital funding 2025 December rounds',
                       'East Africa equity financing opportunities Ethiopia 2025', 
                       'Ethiopia microfinance loans for small businesses 2025 December', 
                       'Ethiopia solar startup grants 2025 December', 
                       ' Horn of Africa tenders 2025 procurement opportunities December',
                       ' Women-owned startups grants Ethiopia 2025 December ']
    # print(refresh_google_queries_task())
    for query in list_of_queries:
        results = google_search(query, num_results=10)
        save_to_registry(results , query)
        print(f' saved the follwing links {results}  for query {query} \n')
        logging.info("Source registry updated successfully.")


if __name__ == "__main__":
    main()
