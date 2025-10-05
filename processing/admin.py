from django.contrib import admin
from .models import ProcessedOpportunity , CleanedOpportunity

admin.site.register(ProcessedOpportunity)
admin.site.register(CleanedOpportunity)