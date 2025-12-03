import os
import json
import logging
from core.utils import init_django
init_django()

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
Given a list of startup profiles and a single funding or partnership opportunity,
decide which startups are relevant for the opportunity.

Return ONLY valid JSON in this format (array of objects, one per startup):
[
  {
    "startup_name": "Startup Name",
    "is_match": true/false,
    "confidence_score": 0.0,
    "justification": ""
  }
]

Guidelines:
- Consider each startup's industry, keywords, country, and description.
- Consider the opportunity's title, description, category, eligibility, and location.
- If a startup could realistically benefit (funding, partnership, or related support),
  return is_match = true with a balanced confidence score (0.7-1.0).
- If unrelated, return is_match = false with a low score (0.0-0.4).
- Evaluate each startup independently.
"""

def get_unmatched_startups(opportunity):
    matched_ids = OpportunityMatch.objects.filter(
        opportunity=opportunity
    ).values_list("startup_id", flat=True)
    return Startup.objects.exclude(id__in=matched_ids)

def match_startups_to_opportunity(opportunity):
    startups = get_unmatched_startups(opportunity)
    if not startups.exists():
        logging.info(f"All startups already matched for {opportunity.title}")
        opportunity.matching_status = "matched"
        opportunity.save(update_fields=["matching_status"])
        return

    logging.info(f"Matching {opportunity.title} with {startups.count()} startups...")

    # Prepare startup batch text
    startups_text = []
    for s in startups:
        startups_text.append(f"""
        Name: {s.name}
        Description: {s.description}
        Industry: {s.industry}
        Country: {s.country}
        Keywords: {s.keywords}
        """)
    startups_text_str = "\n---\n".join(startups_text)

    opportunity_text = f"""
    Title: {opportunity.title}
    Description: {opportunity.description}
    Category: {opportunity.category}
    Eligibility: {opportunity.eligibility}
    Location: {opportunity.location}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "You are a JSON-only evaluator."},
                {"role": "user", "content": MATCHING_PROMPT},
                {"role": "user", "content": f"Startups:\n{startups_text_str}\n\nOpportunity:\n{opportunity_text}"},
            ],
        )

        message = response.choices[0].message
        if not message or not message.content:
            raise ValueError("Empty model response")

        matches = json.loads(message.content.strip())
        any_match = False  # track if at least one startup matched

        for match in matches:
            startup_name = match.get("startup_name")
            is_match = match.get("is_match", False)
            confidence_score = float(match.get("confidence_score", 0.0))
            justification = match.get("justification", "")

            try:
                startup = startups.get(name=startup_name)
            except Startup.DoesNotExist:
                logging.warning(f"Startup {startup_name} not found in DB, skipping")
                continue

            if is_match:
                any_match = True
                OpportunityMatch.objects.update_or_create(
                    opportunity=opportunity,
                    startup=startup,
                    defaults={
                        "confidence_score": confidence_score,
                        "justification": justification,
                        "status": "pending",
                    }
                )
                logging.info(f"Matched: {opportunity.title} → {startup.name} ({confidence_score})")
            else:
                logging.info(f"No match: {opportunity.title} → {startup.name}")

        # Update matching_status based on whether any startup matched
        opportunity.matching_status = "matched" if any_match else "no match"
        opportunity.save(update_fields=["matching_status"])

    except json.JSONDecodeError:
        logging.error(f"Invalid JSON response for opportunity: {opportunity.title}")
    except Exception as e:
        logging.error(f"Error matching startups to {opportunity.title}: {e}")


def run_matching():
    opportunities = ProcessedOpportunity.objects.filter(matching_status="pending").order_by('-created_at')[:15]
    if not opportunities.exists():
        logging.info("No processed opportunities available for matching.")
        return

    logging.info(f"Starting matching for {opportunities.count()} processed opportunities.")
    for opp in opportunities:
        match_startups_to_opportunity(opp)
    logging.info("Matching process completed.")

if __name__ == "__main__":
    run_matching()
