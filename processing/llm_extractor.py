from django.utils import timezone
import os
import json
from core.utils import init_django
init_django()
from django.utils.dateparse import parse_date
from processing.models import CleanedOpportunity, ProcessedOpportunity
from openai import OpenAI
from core.logging import llm_extractor_logger


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

EXTRACTION_PROMPT = """

You are an expert opportunity classifier and extractor.

IMPORTANT:
This task has STRICT PRIORITY RULES.
If a hard rule fails, you MUST immediately reject the opportunity.

HARD RULES (evaluate in order):

1. LANGUAGE CHECK
- If the text is NOT primarily in English → immediately return:
{ "is_opportunity": false, "justification": "Not written in English" }

2. GEOGRAPHIC RELEVANCE (MOST IMPORTANT RULE)
Classify the opportunity location into ONE of the following:
- "ethiopia"
- "horn_of_africa"
- "outside_target_region"

Rules:
- If location is "outside_target_region", you MUST reject immediately.
- Ethiopia has highest priority.
- Horn of Africa is acceptable.


3. DEADLINE VALIDITY
- The opportunity MUST contain a clear deadline.
- The deadline MUST be in the future from today.
- If missing or expired → reject immediately.

ONLY IF ALL HARD RULES PASS Evaluate the following RULES:

4. DOMAIN & OPPORTUNITY CHECK
- Must be related to: fintech, finance, agritech, agriculture, retail, e-commerce, B2B e-commerce, transport, logistics, marketing, IT, investment banking, remittance.
- Must involve funding, grant, equity, Request for proposal (RFP), Expression of interest (EOI), loan, contract.
- Must be an actionable current opportunity (not news about some deal, not past events).

5. Confidence scoring rule:
- Ethiopia-focused opportunities should have confidence ≥ 0.75
- Horn of Africa ≥ 0.6

OUTPUT FORMAT (JSON ONLY):

If rejected:
{
  "is_opportunity": false,
  "rejection_stage": "language | geography | deadline | domain",
  "geo_scope": "",
  "justification": ""
}

If accepted:
{
  "is_opportunity": true,
  "geo_scope": "ethiopia | horn_of_africa ",
  "title": "",
  "description": "",
  "organization": "",
  "category": "",
  "eligibility": "",
  "deadline": "YYYY-MM-DD",
  "location": "",
  "url": "",
  "posted_date": "",
  "confidence_score": 0.0,
  "justification": ""
}

Rules:
- Always return valid JSON ( no markdown or comments )
- Do NOT infer geography if not clearly stated

"""

def extract_opportunity_data(cleaned_opportunity):
    """Send cleaned content to GPT and process if it's a valid opportunity."""
    try:
        response = client.chat.completions.create(
            model="gpt-5.1",
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
            llm_extractor_logger.info(f"Marked as garbage: {cleaned_opportunity.url}")
            return
        
        # case 2: Geographic Failure
        geo_scope = data.get("geo_scope")
        if geo_scope not in ["ethiopia", "horn_of_africa"]:
            cleaned_opportunity.status = "garbage"
            cleaned_opportunity.justification = "Outside target geography"
            cleaned_opportunity.save()
            return

        # case 3: No valid deadline
        deadline_str = data.get("deadline")
        deadline_obj = parse_date(deadline_str) if deadline_str else None
        if not deadline_obj or deadline_obj < timezone.now().date():
            cleaned_opportunity.justification = "Missing or expired deadline"
            cleaned_opportunity.status = "garbage"
            cleaned_opportunity.save()
            llm_extractor_logger.info(f"Marked as garbage due to invalid deadline: {cleaned_opportunity.url}")
            return
        
        # Case 3: Create ProcessedOpportunity
        final_url = data.get("url") or cleaned_opportunity.url
        ProcessedOpportunity.objects.create(
            raw_opportunity=cleaned_opportunity.raw_opportunity,
            title=data.get("title", "")[:500],
            description=data.get("description", ""),
            organization=data.get("organization", ""),
            category=data.get("category", ""),
            eligibility=data.get("eligibility", ""),
            deadline=deadline_obj,
            location=data.get("location", ""),
            url=final_url,
            posted_date=parse_date(data.get("posted_date")) if data.get("posted_date") else None,
            confidence_score=float(data.get("confidence_score", 0.0)),
            justification=data.get("justification", ""),
        )

        cleaned_opportunity.status = "processed"
        cleaned_opportunity.save()
        llm_extractor_logger.info(f"Processed successfully: {cleaned_opportunity.url}")

    except json.JSONDecodeError:
        cleaned_opportunity.status = "garbage"
        cleaned_opportunity.save()
        llm_extractor_logger.warning(f"Invalid JSON for: {cleaned_opportunity.url}")

    except Exception as e:
        llm_extractor_logger.error(f"Error on {cleaned_opportunity.url}: {e}", exc_info=True)


# --- Batch Processing ---
def run_extraction():
    pending_items = CleanedOpportunity.objects.filter(status="pending").order_by('-id')[:30]
    if not pending_items.exists():
        llm_extractor_logger.info("No pending items to process.")
        return

    llm_extractor_logger.info(f"Starting extraction for {pending_items.count()} pending items...")
    for item in pending_items:
        extract_opportunity_data(item)
    llm_extractor_logger.info("Extraction batch completed.")


if __name__ == "__main__":
    run_extraction()
