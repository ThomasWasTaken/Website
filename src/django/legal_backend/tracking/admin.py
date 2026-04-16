# tracking/admin.py

from django.contrib import admin
from .models import ConsultationRequest, Event

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "page", "section", "action", "service", "session_id")
    search_fields = ("page", "section", "action", "service", "session_id", "target")
    list_filter = ("page", "section", "action", "service", "timestamp")
    readonly_fields = ("timestamp", "metadata", "user_agent", "ip_address", "url", "referrer")


@admin.register(ConsultationRequest)
class ConsultationRequestAdmin(admin.ModelAdmin):
    list_display = ("created_at", "name", "email", "phone", "preferred_time", "page")
    search_fields = ("name", "email", "phone", "page", "session_id", "user_id")
    list_filter = ("created_at", "page")
    readonly_fields = ("created_at", "metadata", "session_id", "user_id")
