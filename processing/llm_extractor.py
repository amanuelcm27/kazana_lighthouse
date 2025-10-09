import os
import json
import logging
from core.utils import init_django
init_django()

from django.utils.dateparse import parse_date
from processing.models import CleanedOpportunity, ProcessedOpportunity
from openai import OpenAI

logging.basicConfig(
    filename="core/logs/llm_extractor.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

EXTRACTION_PROMPT = """
You are an expert opportunity classifier and structured information extractor.

Task:
1. Read the provided text carefully.
2. Determine if the text genuinely describes a *funding, grant, project, competition, expression of interest  or contract opportunity*.
3. If it does, extract and return a structured JSON object.
4. If it does NOT contain any meaningful opportunity, return this exact JSON:

{"is_opportunity": false}

If it DOES contain an opportunity, return JSON in the following format:

{
  "is_opportunity": true,
  "title": "",
  "description": "",
  "organization": "",
  "category": "",
  "eligibility": "",
  "deadline": "",
  "location": "",
  "url": "",
  "posted_date": "",
  "confidence_score": 0.0
}

Return ONLY valid JSON. No explanations, no comments, no markdown.
"""

def extract_opportunity_data(cleaned_opportunity):
    """Send cleaned content to GPT and process if it's a valid opportunity."""
    try:
        response = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {"role": "system", "content": "You are a precise JSON-only information extractor."},
                {"role": "user", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": cleaned_opportunity.cleaned_content},
            ],
        )
        print(response)
        message = response.choices[0].message
        if message is None or not message.content:
            raise ValueError("Empty model response")

        raw_output = message.content.strip()
        data = json.loads(raw_output)

        # Case 1: No opportunity found
        if not data.get("is_opportunity", False):
            cleaned_opportunity.status = "garbage"
            cleaned_opportunity.save()
            logging.info(f"Marked as garbage: {cleaned_opportunity.url}")
            return
        final_url = data.get("url") or cleaned_opportunity.url
        # Case 2: Create ProcessedOpportunity
        ProcessedOpportunity.objects.create(
            raw_opportunity=cleaned_opportunity.raw_opportunity,
            title=data.get("title", "")[:500],
            description=data.get("description", ""),
            organization=data.get("organization", ""),
            category=data.get("category", ""),
            eligibility=data.get("eligibility", ""),
            deadline=parse_date(data.get("deadline")) if data.get("deadline") else None,
            location=data.get("location", ""),
            url=final_url,
            posted_date=parse_date(data.get("posted_date")) if data.get("posted_date") else None,
            confidence_score=float(data.get("confidence_score", 0.0)),
        )

        cleaned_opportunity.status = "processed"
        cleaned_opportunity.save()
        logging.info(f"Processed successfully: {cleaned_opportunity.url}")

    except json.JSONDecodeError:
        cleaned_opportunity.status = "garbage"
        cleaned_opportunity.save()
        logging.warning(f"Invalid JSON for: {cleaned_opportunity.url}")

    except Exception as e:
        logging.error(f"Error on {cleaned_opportunity.url}: {e}")


# --- Batch Processing ---
def run_extraction():
    pending_items = CleanedOpportunity.objects.filter(status="pending")[:1]
    if not pending_items.exists():
        logging.info("No pending items to process.")
        return

    logging.info(f"Starting extraction for {pending_items.count()} pending items...")
    for item in pending_items:
        extract_opportunity_data(item)
    logging.info("Extraction batch completed.")


if __name__ == "__main__":
    run_extraction()
