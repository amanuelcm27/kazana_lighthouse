import os
import logging
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from core.utils import init_django
init_django()

from matching.models import OpportunityMatch
from django.conf import settings

# --- Logging setup ---
logging.basicConfig(
    filename="core/logs/email_service.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

CENTRAL_EMAIL0 = getattr(settings, "CENTRAL_NOTIFICATION_EMAIL", os.getenv("CENTRAL_NOTIFICATION_EMAIL"))
CENTRAL_EMAIL1 = getattr(settings, "PRIMARY_NOTIFICATION_EMAIL", os.getenv("PRIMARY_NOTIFICATION_EMAIL"))
CENTRAL_EMAIL2 = getattr(settings, "SECONDARY_NOTIFICATION_EMAIL", os.getenv("SECONDARY_NOTIFICATION_EMAIL"))
CENTRAL_EMAIL3 = getattr(settings, "TERTIARY_NOTIFICATION_EMAIL", os.getenv("TERTIARY_NOTIFICATION_EMAIL"))
DEFAULT_FROM_EMAIL = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@kazana.ai")


def build_central_digest_html(startup_groups):
    """Generate an HTML digest with modern box layout for each opportunity."""
    html_sections = ""

    for startup, matches in startup_groups.items():
        html_sections += f"""
        <h2 style="color:#2c3e50;margin-top:40px;">🚀 Well suited for <strong>{startup.name}</strong></h2>
        <p><em>Industry:</em> {startup.industry or 'N/A'} | 
           <em>Country:</em> {startup.country or 'N/A'} | 
           <em>Keywords:</em> {startup.keywords or 'N/A'}</p>
        """

        for match in matches:
            opp = match.opportunity
            html_sections += f"""
            <div style="
                border: 1px solid #ddd; 
                border-radius: 10px; 
                padding: 20px; 
                margin-bottom: 20px; 
                background: #f9f9f9;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            ">
                <h3 style="margin:0 0 10px 0;color:#1f4e78;">{opp.title}</h3>
                <p style="margin:0 0 5px 0;"><strong>Organization:</strong> {opp.organization or 'N/A'}</p>
                <p style="margin:0 0 5px 0;"><strong>Category:</strong> {opp.category or 'N/A'}</p>
                <p style="margin:0 0 5px 0;"><strong>Deadline:</strong> {opp.deadline or 'N/A'}</p>
                <p style="margin:10px 0;"><strong>Description:</strong> {opp.description}</p>
                <p style="margin:10px 0;background:#eef6fc;padding:10px;border-radius:5px;">
                    <strong>Why this opportunity:</strong> {match.justification or 'N/A'}
                </p>
                <a href="{opp.url or '#'}" style="
                    display:inline-block; 
                    text-decoration:none; 
                    color:#fff; 
                    background:#1f78c1; 
                    padding:10px 15px; 
                    border-radius:5px;
                    margin-top:10px;
                ">View Opportunity</a>
            </div>
            """

    html_content = f"""
    <html>
    <body style="font-family:Arial, sans-serif; color:#333; line-height:1.5;">
        <h1 style="color:#2c3e50;">📬 Kazana Lighthouse Weekly Digest</h1>
        <h2 style="color:#2c3e50;">Found {sum(len(v) for v in startup_groups.values())} new opportunities </h2>
        {html_sections}
        <p style="margin-top:30px;">Best regards,<br><strong>Kazana Lighthouse Team</strong></p>
    </body>
    </html>
    """
    return html_content



def send_central_digest():
    """Send one consolidated digest email to the central company email."""
    if not CENTRAL_EMAIL0 or CENTRAL_EMAIL1 or CENTRAL_EMAIL2 or CENTRAL_EMAIL3:
        logging.error("CENTRAL_NOTIFICATION_EMAIL not configured.")
        return

    pending_matches = OpportunityMatch.objects.filter(mailed_at__isnull=True)

    if not pending_matches.exists():
        logging.info("No pending opportunity matches to email.")
        return

    # Group by startup
    startup_groups = {}
    for match in pending_matches:
        startup_groups.setdefault(match.startup, []).append(match)

    logging.info(f"Preparing digest for {len(startup_groups)} startups...")

    subject = f"📢 {sum(len(v) for v in startup_groups.values())} New Matched Opportunities (Daily Digest)"
    html_body = build_central_digest_html(startup_groups)
    text_body = "You have new matched opportunities for your startups. Please view the HTML version for details."

    try:
        email = EmailMultiAlternatives(subject, text_body, DEFAULT_FROM_EMAIL, [CENTRAL_EMAIL0,CENTRAL_EMAIL1,CENTRAL_EMAIL2,CENTRAL_EMAIL3])
        email.attach_alternative(html_body, "text/html")
        email.send()

        # Mark all as mailed
        for matches in startup_groups.values():
            for match in matches:
                match.mailed_at = timezone.now()
                match.save(update_fields=["mailed_at"])

        logging.info(f"✅ Sent consolidated digest to {CENTRAL_EMAIL0,CENTRAL_EMAIL1, CENTRAL_EMAIL2, CENTRAL_EMAIL3}")

    except Exception as e:
        logging.error(f"❌ Failed to send digest: {e}")


if __name__ == "__main__":
    send_central_digest()
