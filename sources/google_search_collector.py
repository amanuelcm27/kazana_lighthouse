import json
from openai import OpenAI
from urllib.parse import urlparse
from dotenv import load_dotenv
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
import logging
import os
import re
from core.utils import init_django
init_django()
from sources.models import  SourceRegistry
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

    Guidelines:
    - Focus on Horn of Africa, East Africa, with preference for Ethiopia
    - Prefer queries that surface:
        - NGO announcements
        - Development organizations
        - Public tenders
        - Investment programs
    - Include queries that may surface:
        - LinkedIn posts
        - NGO or organization announcements
        - Consulting or procurement notices
    - Prefer queries that surface current or recently announced opportunities (ongoing or upcoming)


    Output ONLY a JSON array of 10 strings.

    
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
    list_of_queries = ['Ethiopia startup funding grant 2025 NGO announcement',
                       'East Africa development grants Ethiopia 2025 site:.org', 
                       'Ethiopia public tenders 2025 development procurement notice',
                       'Ethiopia venture capital program 2025 investment', 
                       'East Africa equity financing opportunities Ethiopia 2025',
                       'Ethiopia loan program government development 2025', 
                       'LinkedIn Ethiopia startup funding grant 2025', 
                       'NGO grant opportunities Ethiopia 2025 development organizations',
                       'Consulting procurement notices Ethiopia 2025 tender', 
                       'Horn of Africa tenders Ethiopia 2025 government portal']
    # print(refresh_google_queries_task())
    for query in list_of_queries:
        results = google_search(query, num_results=10)
        save_to_registry(results, query)
        logging.info("Source registry updated successfully.")


if __name__ == "__main__":
    main()
