import json

from django.test import Client, TestCase

from .models import Event


class TrackEventTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_track_event_creates_database_row(self):
        payload = {
            "page": "testamente",
            "step": "landing",
            "section": "hero",
            "action": "page_view",
            "service": "testamente",
            "target": "/testamente.html",
            "session_id": "session-123",
            "url": "http://localhost:8000/testamente.html",
            "referrer": "http://localhost:8000/",
        }

        response = self.client.post(
            "/api/track/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_USER_AGENT="Test Browser",
            REMOTE_ADDR="127.0.0.1",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Event.objects.count(), 1)

        event = Event.objects.get()
        self.assertEqual(event.page, "testamente")
        self.assertEqual(event.action, "page_view")
        self.assertEqual(event.section, "hero")
        self.assertEqual(event.session_id, "session-123")
        self.assertEqual(event.user_agent, "Test Browser")
        self.assertEqual(event.ip_address, "127.0.0.1")

    def test_track_event_requires_page_and_action(self):
        response = self.client.post(
            "/api/track/",
            data=json.dumps({"page": "testamente"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Event.objects.count(), 0)
