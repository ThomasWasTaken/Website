# tracking/urls.py

from django.urls import path
from .views import track_event, analytics_summary

urlpatterns = [
    path("track/", track_event),
    path("analytics/summary/", analytics_summary),
]