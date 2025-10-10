from django.db import models
from processing.models import ProcessedOpportunity


class Startup(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField()  # free text about what the startup does
    # e.g., Tourism, Fintech, Advertising
    industry = models.CharField(max_length=100)
    country = models.CharField(max_length=100, null=True, blank=True)
    # comma-separated, e.g., "AI, tourism, booking"
    keywords = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class OpportunityMatch(models.Model):
    opportunity = models.ForeignKey(
        ProcessedOpportunity,
        on_delete=models.CASCADE,
        related_name="matches"
    )
    startup = models.ForeignKey(
        Startup,
        on_delete=models.CASCADE,
        related_name="matches"
    )

    confidence_score = models.FloatField(
        default=0.0)  # LLM similarity/match confidence
    status = models.CharField(
        max_length=50,
        choices=[("pending", "Pending"), ("accepted", "Accepted"),
                 ("rejected", "Rejected")],
        default="pending"
    )
    # LLM explanation for the match
    justification = models.TextField(blank=True, null=True)
    matched_at = models.DateTimeField(auto_now_add=True)
    mailed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.opportunity.title} → {self.startup.name}"
