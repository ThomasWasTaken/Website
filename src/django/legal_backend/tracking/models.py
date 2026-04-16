# tracking/models.py

from django.db import models


class Event(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)

    # Agent tracking
    page = models.CharField(max_length=100, db_index=True)
    step = models.CharField(max_length=100, blank=True)
    section = models.CharField(max_length=100, blank=True)

    # Action data
    action = models.CharField(max_length=100, db_index=True)
    service = models.CharField(max_length=100, blank=True, db_index=True)
    target = models.CharField(max_length=255, blank=True)

    # Context
    user_id = models.CharField(max_length=100, blank=True, db_index=True)
    session_id = models.CharField(max_length=100, blank=True, db_index=True)
    url = models.URLField(blank=True)
    referrer = models.URLField(blank=True)
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    # Raw payload (important for flexibility)
    metadata = models.JSONField(default=dict)

    class Meta:
        ordering = ("-timestamp",)

    def __str__(self):
        return f"{self.page} - {self.action}"


class ConsultationRequest(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    message = models.TextField(blank=True)
    preferred_time = models.CharField(max_length=120, blank=True)
    page = models.CharField(max_length=100, blank=True)
    user_id = models.CharField(max_length=100, blank=True, db_index=True)
    session_id = models.CharField(max_length=100, blank=True, db_index=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.name} ({self.email})"
