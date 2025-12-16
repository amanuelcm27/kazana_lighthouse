from django.db import models
from sources.models import RawOpportunity


class ProcessedOpportunity(models.Model):
    raw_opportunity = models.OneToOneField(
        RawOpportunity,
        on_delete=models.CASCADE,
        related_name="processed_opportunity"
    )

    title = models.CharField(max_length=500)
    description = models.TextField()
    organization = models.CharField(max_length=255, null=True, blank=True)
    category = models.CharField(max_length=100, null=True, blank=True)  # e.g., Grant, Accelerator, Fellowship
    eligibility = models.TextField(null=True, blank=True)
    deadline = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)

    url = models.URLField(max_length=500, null=True, blank=True)  # official link
    posted_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    confidence_score = models.FloatField(default=0.0)  # from LLM extraction
    justification = models.TextField(null=True, blank=True)
    matching_status = models.CharField(
        max_length=20,
        choices=[("pending", "Pending"), ("matched", "Matched") , ('no match', "No Match")],
        default="pending",
        help_text="This shows status of specific opportunity matching with a specific startup"
    )
    def __str__(self):
        return f" {self.title[:30]}... | status: {self.matching_status} "


class CleanedOpportunity(models.Model):
    raw_opportunity = models.OneToOneField(
        RawOpportunity,
        on_delete=models.CASCADE,
        related_name='cleaned',
        null=True, blank=True
    )
    source_name = models.CharField(max_length=255)
    url = models.TextField()
    cleaned_content = models.TextField()    
    created_at = models.DateTimeField(auto_now_add=True)
    justification = models.TextField(null=True, blank=True, help_text='justification for garbage status')
    STATUS_CHOICES = [
        ("pending", "Pending LLM Processing"),
        ("processed", "Processed Successfully"),
        ("garbage", "Garbage / Irrelevant"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    def __str__(self):
        return f"Cleaned | {self.source_name} | {self.status}"
