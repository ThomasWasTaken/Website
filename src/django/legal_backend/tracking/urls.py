# tracking/urls.py

from django.urls import path
from .views import analytics_summary, create_consultation_request, simulate_traffic, track_event

urlpatterns = [
    path("track/", track_event),
    path("consultation-request/", create_consultation_request),
    path("simulate/", simulate_traffic),
    path("analytics/summary/", analytics_summary),
]