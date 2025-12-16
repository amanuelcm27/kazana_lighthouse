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
2. Determine if the text is written primarily in English. 
   - If it is NOT in English, return this exact JSON: {"is_opportunity": false}
3. If the text is in English, determine if it explicitly and genuinely follows the following rules : 
- Only consider opportunities related to **fin-tech, finance, agritech, agriculture, retail ,  e-commerce , b2b e-commerce ,transport , logistics marketing,  Information technology , investment banking  , remittance**.
- Only consider opportunities including *funding, grant, equity ,  project, competition, request for proposal , loans , expression of interest, rfp , eoi , or contract opportunity*
- Only conisder opportunities that are relevant to Ethiopian companies.
- Generic mentions such as “looking for funding” or “apply now” without clear details of a specific opportunity are NOT valid.
- The content must clearly state at least one specific opportunity or call for application.
4. If no meaningful opportunity is found, return this exact JSON:
   {"is_opportunity": false}
5. If a real opportunity is identified, extract and return a structured JSON object in this format:

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
  "confidence_score": 0.0,
  "justification": "", # short explanation of why it is or not an opportunity
}

Rules:
- Always return ONLY valid JSON (no markdown or comments).
- If the source text does not contain a valid opportunity, return {"is_opportunity": false}.

"""

def extract_opportunity_data(cleaned_opportunity):
    """Send cleaned content to GPT and process if it's a valid opportunity."""
    try:
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "You are a precise JSON-only information extractor."},
                {"role": "user", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": cleaned_opportunity.cleaned_content},
            ],
        )

        message = response.choices[0].message
        if message is None or not message.content:
            raise ValueError("Empty model response")

        raw_output = message.content.strip()
        data = json.loads(raw_output)

        # Case 1: No opportunity found
        if not data.get("is_opportunity", False):
            cleaned_opportunity.justification = data.get("justification", "")
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
            justification=data.get("justification", ""),
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
    pending_items = CleanedOpportunity.objects.filter(status="pending").order_by('-id')[:15]
    if not pending_items.exists():
        logging.info("No pending items to process.")
        return

    logging.info(f"Starting extraction for {pending_items.count()} pending items...")
    for item in pending_items:
        extract_opportunity_data(item)
    logging.info("Extraction batch completed.")


if __name__ == "__main__":
    run_extraction()
