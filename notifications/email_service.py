import os
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from core.utils import init_django
init_django()
from core.logging import email_logger
from matching.models import OpportunityMatch
from processing.models import ProcessedOpportunity
from django.conf import settings




# Load emails
CENTRAL_EMAIL0 = getattr(settings, "CENTRAL_NOTIFICATION_EMAIL", os.getenv("CENTRAL_NOTIFICATION_EMAIL"))
CENTRAL_EMAIL1 = getattr(settings, "PRIMARY_NOTIFICATION_EMAIL", os.getenv("PRIMARY_NOTIFICATION_EMAIL"))
CENTRAL_EMAIL2 = getattr(settings, "SECONDARY_NOTIFICATION_EMAIL", os.getenv("SECONDARY_NOTIFICATION_EMAIL"))
CENTRAL_EMAIL3 = getattr(settings, "TERTIARY_NOTIFICATION_EMAIL", os.getenv("TERTIARY_NOTIFICATION_EMAIL"))
DEFAULT_FROM_EMAIL = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@kazana.ai")


# ============================================================
#               HTML BUILDER — GROUPED BY OPPORTUNITY
# ============================================================

def build_central_digest_html(opportunity_groups,unmatched_opps):
    """Generate HTML digest grouped under each opportunity with all startups and their justifications."""

    html_sections = ""
    unmatched_sections = ''
    for opp in unmatched_opps:
        unmatched_sections += f"""
            <div style="
            border: 1px solid #ddd; 
            border-radius: 10px; 
            padding: 20px; 
            margin-bottom: 30px; 
            background: #fafafa;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        ">
            <h2 style="color:#1f4e78;margin:0 0 10px 0;">{opp.title}</h2>

            <p style="margin:0 0 6px 0;"><strong>Organization:</strong> {opp.organization or "N/A"}</p>
            <p style="margin:0 0 6px 0;"><strong>Category:</strong> {opp.category or "N/A"}</p>
            <p style="margin:0 0 10px 0;"><strong>Deadline:</strong> {opp.deadline or "N/A"}</p>

            <p style="margin-top:10px;"><strong>Description:</strong> {opp.description or 'N/A'}</p>


        """


        unmatched_sections += f"""

            <a href="{opp.url or '#'}" style="
                display:inline-block;
                margin-top:16px;
                padding:10px 15px;
                text-decoration:none;
                color:white;
                background:#1f78c1;
                border-radius:6px;
            ">View Opportunity</a>
        </div>
        """
    for opp, matches in opportunity_groups.items():

        html_sections += f"""
        <div style="
            border: 1px solid #ddd; 
            border-radius: 10px; 
            padding: 20px; 
            margin-bottom: 30px; 
            background: #fafafa;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        ">
            <h2 style="color:#1f4e78;margin:0 0 10px 0;">{opp.title}</h2>

            <p style="margin:0 0 6px 0;"><strong>Organization:</strong> {opp.organization or "N/A"}</p>
            <p style="margin:0 0 6px 0;"><strong>Category:</strong> {opp.category or "N/A"}</p>
            <p style="margin:0 0 10px 0;"><strong>Deadline:</strong> {opp.deadline or "N/A"}</p>

            <p style="margin-top:10px;"><strong>Description:</strong> {opp.description or 'N/A'}</p>

            <h3 style="margin-top:20px;color:#2c3e50;">Matched for Startups:</h3>
            <ul style="margin-top:6px;padding-left:18px;">
        """

        for match in matches:
            startup = match.startup
            justification = (match.justification or "").strip()
            justification_html = f"<div style='margin-top:6px;padding:8px;background:#eef6fc;border-radius:6px;'><strong>Why this match:</strong> {justification}</div>" if justification else ""

            html_sections += f"""
                <li style="margin-bottom:8px;">
                    <strong>{startup.name}</strong> 
                    – {startup.industry or 'N/A'} 
                    – {startup.country or 'N/A'}
                    {justification_html}
                </li>
            """

        html_sections += f"""
            </ul>

            <a href="{opp.url or '#'}" style="
                display:inline-block;
                margin-top:16px;
                padding:10px 15px;
                text-decoration:none;
                color:white;
                background:#1f78c1;
                border-radius:6px;
            ">View Opportunity</a>
        </div>
        """

    # Wrap full email
    html_body = f"""
    <html>
    <body style="font-family:Arial, sans-serif; color:#333; line-height:1.6;">
        <h1 style="color:#2c3e50;">📬 Kazana Lighthouse Weekly Digest</h1>
        <h2 style="color:#2c3e50;">Found {len(opportunity_groups)} Unique Opportunities</h2>

        {html_sections}

        
        <p style="margin-top:40px;">
            Best regards,<br>
            <strong>Kazana Lighthouse Team</strong>
        </p>
    </body>
    </html>

    """

    return html_body


# ============================================================
#                  SEND DIGEST EMAIL
# ============================================================

from django.db.models import Max

def send_central_digest():
    """Send consolidated digest email for top 6 highly scoring opportunity matches."""

    emails = [CENTRAL_EMAIL0, CENTRAL_EMAIL1, CENTRAL_EMAIL2, CENTRAL_EMAIL3]
    emails = [e for e in emails if e]
    if not emails:
        email_logger.error("No central notification emails configured.", exc_info=True)
        return

    # Annotate opportunities with their max confidence score
    top_opportunity_ids = (
        OpportunityMatch.objects
        .filter(mailed_at__isnull=True)
        .values('opportunity')
        .annotate(max_confidence=Max('confidence_score'))
        .order_by('-max_confidence')[:6]  # Take top 6 opportunities
        .values_list('opportunity', flat=True)
    )

    if not top_opportunity_ids:
        email_logger.info("No opportunity matches to email.")
        return

    # Fetch matches for these top opportunities
    pending_matches = (
        OpportunityMatch.objects
        .filter(opportunity_id__in=top_opportunity_ids, mailed_at__isnull=True)
        .select_related('opportunity', 'startup')
    )

    # Group matches by opportunity
    opportunity_groups = {}
    for match in pending_matches:
        opp = match.opportunity
        opportunity_groups.setdefault(opp, []).append(match)

    # Fetch unmatched opportunities if needed
    unmatched_opps = ProcessedOpportunity.objects.filter(matching_status='no match')

    email_logger.info(f"Preparing digest for top {len(opportunity_groups)} opportunities...")

    # Build email content
    subject = f"📢 {len(opportunity_groups)} New High-Scoring Opportunities (Weekly Digest)"
    html_body = build_central_digest_html(opportunity_groups, unmatched_opps)
    text_body = "You have new high-scoring matched opportunities. Please view the HTML version for details."

    try:
        email = EmailMultiAlternatives(
            subject,
            text_body,
            DEFAULT_FROM_EMAIL,
            emails
        )
        email.attach_alternative(html_body, "text/html")
        email.send()

        # Mark matches as mailed
        now = timezone.now()
        for matches in opportunity_groups.values():
            for match in matches:
                match.mailed_at = now
                match.save(update_fields=["mailed_at"])

        email_logger.info(f"✅ Sent digest to central emails: {emails}. Opportunities: {len(opportunity_groups)}")

    except Exception as e:
        email_logger.error(f"Failed to send digest: {e}", exc_info=True)


if __name__ == "__main__":
    send_central_digest()
