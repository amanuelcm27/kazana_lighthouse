# sources/models.py
from django.db import models

class RawOpportunity(models.Model):
    SOURCE_TYPES = [
        ('static', 'Static HTML Page'),
        ('dynamic', 'Dynamic JS Page'),
        ('api', 'API'),
        ('rss', 'RSS Feed'),
        ('file', 'PDF/Image'),
    ]

    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    source_name = models.TextField()  
    url = models.TextField(blank=True, null=True)  
    raw_content = models.TextField() 
    file_name = models.TextField(blank=True, null=True)  
    fetched_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)

    STATUS_CHOICES = [
        ("pending", "Pending Processing"),
        ("valid", "Valid Opportunity"),
        ("garbage", "Garbage / Irrelevant"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    
    def __str__(self):
        return f"{self.source_name} | {self.source_type} | fetched {self.fetched_at}"



class SourceRegistry(models.Model):
    SOURCE_TYPES = [
        ('google', "Google Search Result"),
        ("custom", "Manually Added Source")
    ]
    WEB_TYPES = [
        ('static', 'Static HTML Page'),
        ('dynamic', 'Dynamic JS Page'),
      
    ]
    name = models.CharField(max_length=255)          # e.g., un.org, grants.gov
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    base_url = models.URLField()
    active = models.BooleanField(default=True)       
    web_type = models.CharField(max_length=20, choices=WEB_TYPES, default='static')
    last_scraped = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} | {self.source_type}"
