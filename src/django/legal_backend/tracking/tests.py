import json

from django.test import Client, TestCase

from .models import ConsultationRequest, Event
from .views import _pct_change


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
            "user_id": "user-001",
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
        self.assertEqual(event.user_id, "user-001")
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


class AnalyticsSummaryTests(TestCase):
    def setUp(self):
        self.client = Client()

        Event.objects.create(
            page="testamente",
            action="page_view",
            section="page",
            user_id="user-1",
            session_id="session-1",
            metadata={"source_channel": "organic"},
        )
        Event.objects.create(
            page="testamente",
            action="primary_navigation_click",
            section="hero",
            user_id="user-1",
            session_id="session-1",
            target="/legal_site_agentveiw.html",
            metadata={"source_channel": "organic"},
        )
        Event.objects.create(
            page="testamente",
            action="page_view",
            section="page",
            user_id="user-2",
            session_id="session-2",
            metadata={"source_channel": "paid"},
        )

    def test_analytics_summary_includes_enhanced_metrics(self):
        response = self.client.get("/api/analytics/summary/")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["kpis"]["users"], 2)
        self.assertEqual(payload["kpis"]["sessions"], 2)
        self.assertIn("events_per_session", payload["kpis"])
        self.assertIn("drop_offs", payload)
        self.assertIn("insights", payload)
        self.assertIn("alerts", payload["insights"])
        self.assertIn("trends", payload["insights"])
        self.assertIn("book_appointment_cvr_pct", payload["kpis"])
        self.assertIn("engagement_timeseries", payload)
        self.assertTrue(any(row["channel"] == "organic" for row in payload["channels"]))

    def test_book_appointment_cvr_uses_consultation_page_view_denominator(self):
        Event.objects.create(
            page="juridisk-konsultation",
            action="page_view",
            section="page",
            user_id="user-a",
            session_id="session-a",
            metadata={"source_channel": "page:legal_site"},
        )
        Event.objects.create(
            page="juridisk-konsultation",
            action="page_view",
            section="page",
            user_id="user-b",
            session_id="session-b",
            metadata={"source_channel": "page:legal_site"},
        )
        Event.objects.create(
            page="juridisk-konsultation",
            action="appointment_booked",
            section="consultation-form",
            user_id="user-a",
            session_id="session-a",
            metadata={"source_channel": "page:legal_site"},
        )
        response = self.client.get("/api/analytics/summary/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["kpis"]["book_appointment_cvr_pct"], 50.0)

    def test_channel_summary_uses_session_primary_channel_for_bookings(self):
        Event.objects.create(
            page="juridisk-konsultation",
            action="page_view",
            section="page",
            user_id="user-c",
            session_id="session-c",
            metadata={"source_channel": "page:legal_site"},
        )
        Event.objects.create(
            page="juridisk-konsultation",
            action="appointment_booked",
            section="consultation-form",
            user_id="user-c",
            session_id="session-c",
            metadata={"source_channel": "direct"},
        )
        response = self.client.get("/api/analytics/summary/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        legal_site_row = next((row for row in payload["channels"] if row["channel"] == "page:legal_site"), None)
        self.assertIsNotNone(legal_site_row)
        self.assertGreaterEqual(legal_site_row["conversions"], 1)


class ConsultationRequestTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_create_consultation_request(self):
        payload = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "+4511122233",
            "message": "I need help choosing the right legal document.",
            "preferred_time": "Tuesday after 16:00",
            "page": "juridisk-konsultation",
            "user_id": "user-xyz",
            "session_id": "session-xyz",
        }
        response = self.client.post(
            "/api/consultation-request/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ConsultationRequest.objects.count(), 1)
        self.assertEqual(Event.objects.filter(action="appointment_booked").count(), 1)
        request_row = ConsultationRequest.objects.get()
        self.assertEqual(request_row.name, "Jane Doe")
        self.assertEqual(request_row.email, "jane@example.com")

    def test_create_consultation_request_requires_name_and_email(self):
        response = self.client.post(
            "/api/consultation-request/",
            data=json.dumps({"name": "Only Name"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ConsultationRequest.objects.count(), 0)

    def test_track_event_defaults_channel_to_direct_without_referrer(self):
        payload = {
            "page": "testamente",
            "action": "page_view",
            "session_id": "session-direct",
            "user_id": "user-direct",
        }
        response = self.client.post(
            "/api/track/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        event = Event.objects.get(session_id="session-direct")
        self.assertEqual(event.metadata.get("source_channel"), "direct")

    def test_track_event_maps_internal_referrer_to_page_channel(self):
        payload = {
            "page": "testamente",
            "action": "page_view",
            "session_id": "session-page-ref",
            "user_id": "user-page-ref",
            "referrer": "http://0.0.0.0:8000/juridisk-konsultation.html",
        }
        response = self.client.post(
            "/api/track/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        event = Event.objects.get(session_id="session-page-ref")
        self.assertEqual(event.metadata.get("source_channel"), "page:juridisk-konsultation")


class SimulationTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_simulate_endpoint_generates_events(self):
        response = self.client.post(
            "/api/simulate/",
            data=json.dumps({"users": 5, "min_sessions": 1, "max_sessions": 2, "seed": 42, "password": "simulate"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertGreater(payload["events_inserted"], 0)
        self.assertGreater(Event.objects.count(), 0)

    def test_simulate_endpoint_requires_password(self):
        response = self.client.post(
            "/api/simulate/",
            data=json.dumps({"users": 5, "min_sessions": 1, "max_sessions": 2, "password": "wrong"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)


class TrendMathTests(TestCase):
    def test_zero_to_two_shows_two_hundred_pct_change(self):
        self.assertEqual(_pct_change(0, 2), 200.0)
