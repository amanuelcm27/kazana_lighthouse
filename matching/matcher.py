import os
import json
import logging
from core.utils import init_django
init_django()

from django.db.models import Q
from openai import OpenAI
from processing.models import ProcessedOpportunity
from .models import Startup, OpportunityMatch


logging.basicConfig(
    filename="core/logs/matcher.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MATCHING_PROMPT = """
You are a precise opportunity-startup matcher.

Your job:
Given a startup profile and a description of a funding or partnership opportunity,
decide whether the opportunity is relevant for the startup.

Return ONLY valid JSON in this format:
{
  "is_match": true/false,
  "confidence_score": 0.0,
  "justification": ""
}

Guidelines:
- Consider the startup's industry, keywords, country and description.
- Consider the opportunity's title, description, category, and eligibility.
- If the startup could realistically benefit (funding, partnership, or related support),
  return is_match = true with a balanced confidence score (0.7-1.0).
- If unrelated, return is_match = false with a low score (0.0-0.4).
"""

def get_unmatched_startups(opportunity):
    matched_startup_ids = OpportunityMatch.objects.filter(
        opportunity=opportunity
    ).values_list("startup_id", flat=True)

    return Startup.objects.exclude(id__in=matched_startup_ids)

# --- Matching logic ---
def match_startups_to_opportunity(opportunity):
    startups = get_unmatched_startups(opportunity)
    if not startups.exists():
        logging.info(f"All startups already matched for {opportunity.title}")
        opportunity.matching_status = "matched"
        print("All startups already matched.")
        opportunity.save(update_fields=["matching_status"])
        return

    logging.info(f"Matching {opportunity.title} with {startups.count()} remaining startups...")


    for startup in startups:
        try:
            startup_text = f"""
            Name: {startup.name}
            Description: {startup.description}
            Industry: {startup.industry}
            Country: {startup.country}
            Keywords: {startup.keywords}
            """

            opportunity_text = f"""
            Title: {opportunity.title}
            Description: {opportunity.description}
            Category: {opportunity.category}
            Eligibility: {opportunity.eligibility}
            Location: {opportunity.location}
            """

            response = client.chat.completions.create(
                model="gpt-5-nano",
                messages=[
                    {"role": "system", "content": "You are a JSON-only evaluator."},
                    {"role": "user", "content": MATCHING_PROMPT},
                    {"role": "user", "content": f"Startup:\n{startup_text}\n\nOpportunity:\n{opportunity_text}"},
                ],
            )

            message = response.choices[0].message
            if message is None or not message.content:
                raise ValueError("Empty model response")

            data = json.loads(message.content.strip())

            # --- If it's a match, create or update the record ---
            if data.get("is_match"):
                OpportunityMatch.objects.update_or_create(
                    opportunity=opportunity,
                    startup=startup,
                    defaults={
                        "confidence_score": float(data.get("confidence_score", 0.0)),
                        "justification": data.get("justification", ""),
                        "status": "pending",
                    }
                )
                logging.info(f"Matched: {opportunity.title} → {startup.name} ({data.get('confidence_score', 0.0)})")

            else:
                logging.info(f"No match: {opportunity.title} → {startup.name}")

        except json.JSONDecodeError:
            logging.warning(f"Invalid JSON for {startup.name} and {opportunity.title}")
        except Exception as e:
            logging.error(f"Error matching {startup.name} to {opportunity.title}: {e}")

def run_matching():
    opportunities = ProcessedOpportunity.objects.filter(matching_status="pending").order_by('-created_at')[:5]
    if not opportunities.exists():
        logging.info("No processed opportunities available for matching.")
        return

    logging.info(f" Starting matching for {opportunities.count()} processed opportunities.")
    for opp in opportunities:
        match_startups_to_opportunity(opp)

    logging.info( " Matching process completed." )


if __name__ == "__main__":
    run_matching()
