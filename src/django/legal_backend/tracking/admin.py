# tracking/admin.py

from django.contrib import admin
from .models import Event

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "page", "section", "action", "service", "session_id")
    search_fields = ("page", "section", "action", "service", "session_id", "target")
    list_filter = ("page", "section", "action", "service", "timestamp")
    readonly_fields = ("timestamp", "metadata", "user_agent", "ip_address", "url", "referrer")
