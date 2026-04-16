import json
from collections import Counter, defaultdict
from datetime import timedelta
from ipaddress import ip_address
from urllib.parse import urlparse

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import ConsultationRequest, Event
from .simulation import run_simulation_to_db

ALLOWED_TRACKING_PAGES = {
    "legal_site_agentveiw",
    "forside",
    "testamente",
    "ægtepagt",
    "samejeoverenskomst",
    "fuldmagt",
    "juridisk-konsultation",
    "lejekontrakt",
}
INTERNAL_REFERRER_HOSTS = {
    "0.0.0.0",
    "127.0.0.1",
    "localhost",
    "web",
    "thomas-lund-code.com",
    "www.thomas-lund-code.com",
}
SIMULATION_PASSWORD = "simulate"


def _cors_json(data, status=200):
    response = JsonResponse(data, status=status)
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response["Access-Control-Allow-Headers"] = "Content-Type"
    return response


def _client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    candidate = forwarded_for.split(",")[0].strip() if forwarded_for else request.META.get("REMOTE_ADDR", "")
    if not candidate:
        return None
    try:
        return str(ip_address(candidate))
    except ValueError:
        return None


def _pct_change(previous, current):
    if previous == 0:
        # Use a 1-unit baseline proxy when previous is zero so 0->N
        # scales with magnitude (e.g. 0->2 => 200%) instead of fixed 100%.
        return round(current * 100.0, 2) if current > 0 else 0.0
    return round(((current - previous) / previous) * 100, 2)


def _trend_label(previous, current, threshold_pct=12.0):
    change_pct = _pct_change(previous, current)
    if change_pct >= threshold_pct:
        return "up", change_pct
    if change_pct <= -threshold_pct:
        return "down", change_pct
    return "stable", change_pct


def _channel_from_referrer(referrer):
    raw = (referrer or "").strip()
    if not raw:
        return "direct"
    try:
        hostname = urlparse(raw).hostname or ""
    except ValueError:
        return "direct"
    normalized = hostname.replace("www.", "").strip().lower()
    if not normalized:
        return "direct"
    return f"ref:{normalized}"


def _page_channel_from_referrer(referrer):
    raw = (referrer or "").strip()
    if not raw:
        return "direct"
    try:
        parsed = urlparse(raw)
    except ValueError:
        return "direct"

    hostname = (parsed.hostname or "").replace("www.", "").strip().lower()
    if not hostname:
        return "direct"

    if hostname not in INTERNAL_REFERRER_HOSTS:
        return f"ref:{hostname}"

    path = (parsed.path or "").strip("/")
    if not path:
        return "page:home"

    page_slug = path.split("/")[-1].replace(".html", "").strip().lower()
    if not page_slug:
        return "page:home"
    if page_slug in {"index", "index_light", "index_light copy"}:
        return "page:home"
    return f"page:{page_slug}"


def _normalize_source_channel(source_channel, referrer):
    channel = (source_channel or "").strip()
    if not channel:
        return _page_channel_from_referrer(referrer)
    if channel.startswith("ref:"):
        ref_host = channel.replace("ref:", "", 1).strip().lower()
        if ref_host in INTERNAL_REFERRER_HOSTS:
            return _page_channel_from_referrer(referrer)
    if channel == "unknown":
        return _page_channel_from_referrer(referrer)
    return channel


def _resolve_source_channel(data, metadata, referrer):
    explicit = (
        (data.get("source_channel") or "").strip()
        or (data.get("channel_id") or "").strip()
        or (data.get("utm_source") or "").strip()
        or (metadata.get("source_channel") or "").strip()
    )
    return _normalize_source_channel(explicit, referrer)


@csrf_exempt
def track_event(request):
    if request.method == "OPTIONS":
        return _cors_json({"status": "ok"})

    if request.method != "POST":
        return _cors_json({"error": "invalid request"}, status=400)

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _cors_json({"error": "invalid json"}, status=400)

    page = (data.get("page") or "").strip()
    action = (data.get("action") or "").strip()

    if not page or not action:
        return _cors_json({"error": "page and action are required"}, status=400)
    if page not in ALLOWED_TRACKING_PAGES:
        return _cors_json({"status": "ignored", "reason": "page not tracked"})

    metadata = data.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {"raw_metadata": metadata}

    referrer = (data.get("referrer") or "").strip()
    source_channel = _resolve_source_channel(data, metadata, referrer)
    metadata["source_channel"] = source_channel

    Event.objects.create(
        page=page,
        step=(data.get("step") or "").strip(),
        section=(data.get("section") or "").strip(),
        action=action,
        service=(data.get("service") or "").strip(),
        target=(data.get("target") or "").strip()[:255],
        user_id=(data.get("user_id") or "").strip(),
        session_id=(data.get("session_id") or "").strip(),
        url=(data.get("url") or "").strip(),
        referrer=referrer,
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        ip_address=_client_ip(request),
        metadata=metadata,
    )

    return _cors_json({"status": "ok"})


@csrf_exempt
def create_consultation_request(request):
    if request.method == "OPTIONS":
        return _cors_json({"status": "ok"})

    if request.method != "POST":
        return _cors_json({"error": "invalid request"}, status=400)

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _cors_json({"error": "invalid json"}, status=400)

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    if not name or not email:
        return _cors_json({"error": "name and email are required"}, status=400)

    referrer = (data.get("referrer") or "").strip()
    metadata = data if isinstance(data, dict) else {"raw_payload": data}
    source_channel = _resolve_source_channel(data, metadata, referrer)
    metadata["source_channel"] = source_channel

    consultation = ConsultationRequest.objects.create(
        name=name,
        email=email,
        phone=(data.get("phone") or "").strip(),
        message=(data.get("message") or "").strip(),
        preferred_time=(data.get("preferred_time") or "").strip(),
        page=(data.get("page") or "").strip(),
        user_id=(data.get("user_id") or "").strip(),
        session_id=(data.get("session_id") or "").strip(),
        metadata=metadata,
    )
    Event.objects.create(
        page=(data.get("page") or "juridisk-konsultation").strip() or "juridisk-konsultation",
        step="booking",
        section="consultation-form",
        action="appointment_booked",
        service="juridisk-konsultation",
        target=str(consultation.id),
        user_id=(data.get("user_id") or "").strip(),
        session_id=(data.get("session_id") or "").strip(),
        url=(data.get("url") or "").strip(),
        referrer=referrer,
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        ip_address=_client_ip(request),
        metadata=metadata,
    )
    return _cors_json({"status": "ok"})


@csrf_exempt
def analytics_summary(request):
    if request.method == "OPTIONS":
        return _cors_json({"status": "ok"})

    if request.method != "GET":
        return _cors_json({"error": "invalid request"}, status=400)

    events = list(
        Event.objects.filter(page__in=ALLOWED_TRACKING_PAGES).values(
            "timestamp",
            "page",
            "section",
            "user_id",
            "session_id",
            "action",
            "target",
            "referrer",
            "metadata",
        )
    )

    total_events = len(events)
    unique_sessions = {item["session_id"] for item in events if item["session_id"]}
    unique_users = {item["user_id"] for item in events if item["user_id"]}

    conversion_actions = {"appointment_booked"}
    conversion_events = [item for item in events if item["action"] in conversion_actions]
    hero_views = [
        item
        for item in events
        if item["action"] == "section_view" and (item.get("section") or "").strip() == "hero"
    ]
    scroll_events = [item for item in events if item["action"] == "scroll_depth"]

    funnel_actions = [
        ("Landing", "page_view"),
        ("Pricing Viewed", "view_pricing"),
        ("Form Viewed", "view_consultation-form"),
        ("Booking Intent", "consultation_form_submit"),
        ("Appointment Booked", "appointment_booked"),
    ]

    funnel = []
    funnel_sessions_sequence = []
    for label, action_name in funnel_actions:
        sessions_for_action = set()
        for item in events:
            if action_name == "hero_view":
                if item["action"] != "section_view" or (item.get("section") or "").strip() != "hero":
                    continue
            elif action_name.startswith("view_"):
                section_name = action_name.replace("view_", "", 1)
                if item["action"] != "section_view" or (item.get("section") or "").strip() != section_name:
                    continue
            elif action_name == "subpage_click":
                if item["action"] not in {"service_card_click", "module_click"}:
                    continue
            elif item["action"] != action_name:
                continue
            metadata = item.get("metadata") or {}
            if action_name == "scroll_depth" and metadata.get("scroll_percent", 0) < 50:
                continue
            if item["session_id"]:
                sessions_for_action.add(item["session_id"])
        funnel.append({"step": label, "sessions": len(sessions_for_action)})
        funnel_sessions_sequence.append(sessions_for_action)

    drop_offs = []
    for idx in range(len(funnel_sessions_sequence) - 1):
        current_sessions = funnel_sessions_sequence[idx]
        next_sessions = funnel_sessions_sequence[idx + 1]
        retained = len(current_sessions.intersection(next_sessions))
        total_current = len(current_sessions)
        dropped = max(total_current - retained, 0)
        drop_rate = round((dropped / total_current) * 100, 2) if total_current else 0.0
        drop_offs.append(
            {
                "from_step": funnel[idx]["step"],
                "to_step": funnel[idx + 1]["step"],
                "sessions_start": total_current,
                "sessions_retained": retained,
                "drop_off_sessions": dropped,
                "drop_off_rate_pct": drop_rate,
            }
        )

    channel_sessions = defaultdict(set)
    channel_events = Counter()
    channel_conversions = Counter()
    session_primary_channel = {}
    for item in sorted(events, key=lambda row: row["timestamp"]):
        session_id = item.get("session_id") or ""
        if not session_id or session_id in session_primary_channel:
            continue
        metadata = item.get("metadata") or {}
        direct_channel = _normalize_source_channel((metadata.get("source_channel") or "").strip(), item.get("referrer"))
        session_primary_channel[session_id] = direct_channel

    for item in events:
        metadata = item.get("metadata") or {}
        direct_channel = _normalize_source_channel((metadata.get("source_channel") or "").strip(), item.get("referrer"))
        channel = session_primary_channel.get(item.get("session_id") or "", direct_channel)
        if item["session_id"]:
            channel_sessions[channel].add(item["session_id"])
        channel_events[channel] += 1
        if item["action"] in conversion_actions:
            channel_conversions[channel] += 1

    channels = []
    for channel in sorted(channel_events.keys()):
        session_ids = channel_sessions[channel]
        user_ids = {
            item["user_id"]
            for item in events
            if (
                session_primary_channel.get(item.get("session_id") or "", _normalize_source_channel(
                    ((item.get("metadata") or {}).get("source_channel") or "").strip(),
                    item.get("referrer"),
                )) == channel
                and item.get("user_id")
            )
        }
        session_count = len(session_ids)
        conversions = channel_conversions[channel]
        channels.append(
            {
                "channel": channel,
                "users": len(user_ids),
                "sessions": session_count,
                "events": channel_events[channel],
                "conversions": conversions,
                "conversion_rate_pct": round((conversions / session_count) * 100, 2) if session_count else 0.0,
            }
        )
    channels.sort(key=lambda row: row["sessions"], reverse=True)

    first_touch = {}
    for item in sorted(events, key=lambda row: row["timestamp"]):
        session_id = item["session_id"]
        if session_id and session_id not in first_touch:
            first_touch[session_id] = item["timestamp"].date().isoformat()

    cohort_activity = defaultdict(set)
    for item in events:
        session_id = item["session_id"]
        if not session_id or session_id not in first_touch:
            continue
        cohort_date = first_touch[session_id]
        event_date = item["timestamp"].date().isoformat()
        cohort_activity[(cohort_date, event_date)].add(session_id)

    cohorts = [
        {"cohort_date": cohort_date, "event_date": event_date, "active_sessions": len(session_ids)}
        for (cohort_date, event_date), session_ids in sorted(cohort_activity.items())
    ]

    cohort_summary = defaultdict(lambda: {"sessions": set(), "returning_sessions": set()})
    for (cohort_date, event_date), session_ids in cohort_activity.items():
        cohort_summary[cohort_date]["sessions"].update(session_ids)
        if event_date > cohort_date:
            cohort_summary[cohort_date]["returning_sessions"].update(session_ids)
    cohort_retention = []
    for cohort_date, stats in sorted(cohort_summary.items()):
        cohort_size = len(stats["sessions"])
        retained = len(stats["returning_sessions"])
        cohort_retention.append(
            {
                "cohort_date": cohort_date,
                "cohort_size": cohort_size,
                "returning_sessions": retained,
                "retention_rate_pct": round((retained / cohort_size) * 100, 2) if cohort_size else 0.0,
            }
        )

    top_targets = Counter()
    for item in conversion_events:
        target = item.get("target") or "(no target)"
        top_targets[target] += 1

    now = timezone.now()
    recent_start = now - timedelta(minutes=5)
    previous_start = now - timedelta(minutes=10)
    recent_events = [item for item in events if item["timestamp"] >= recent_start]
    previous_events = [item for item in events if previous_start <= item["timestamp"] < recent_start]
    timeseries_start = now - timedelta(hours=24)
    timeseries_events = [item for item in events if item["timestamp"] >= timeseries_start]

    bucket_totals = defaultdict(lambda: {"events": 0, "engagement": 0, "bookings": 0})
    for item in timeseries_events:
        bucket_dt = item["timestamp"].replace(minute=0, second=0, microsecond=0)
        bucket_key = bucket_dt.isoformat()
        bucket_totals[bucket_key]["events"] += 1
        if item["action"] in {"scroll_depth", "section_view", "click_cta", "consultation_form_submit"}:
            bucket_totals[bucket_key]["engagement"] += 1
        if item["action"] == "appointment_booked":
            bucket_totals[bucket_key]["bookings"] += 1

    engagement_timeseries = []
    for i in range(24):
        point_dt = (timeseries_start + timedelta(hours=i + 1)).replace(minute=0, second=0, microsecond=0)
        point_key = point_dt.isoformat()
        bucket = bucket_totals[point_key]
        engagement_timeseries.append(
            {
                "timestamp": point_key,
                "events": bucket["events"],
                "engagement_events": bucket["engagement"],
                "bookings": bucket["bookings"],
            }
        )

    recent_sessions = {item["session_id"] for item in recent_events if item["session_id"]}
    previous_sessions = {item["session_id"] for item in previous_events if item["session_id"]}
    recent_users = {item["user_id"] for item in recent_events if item["user_id"]}
    previous_users = {item["user_id"] for item in previous_events if item["user_id"]}
    recent_conversion_sessions = {
        item["session_id"] for item in recent_events if item["action"] in conversion_actions and item["session_id"]
    }
    previous_conversion_sessions = {
        item["session_id"] for item in previous_events if item["action"] in conversion_actions and item["session_id"]
    }

    session_trend, session_change_pct = _trend_label(len(previous_sessions), len(recent_sessions))
    conversion_trend, conversion_change_pct = _trend_label(
        len(previous_conversion_sessions), len(recent_conversion_sessions)
    )
    user_trend, user_change_pct = _trend_label(len(previous_users), len(recent_users))

    alerts = []
    if funnel and funnel[0]["sessions"] > 0:
        last_step_sessions = funnel[-1]["sessions"]
        funnel_completion_rate = round((last_step_sessions / funnel[0]["sessions"]) * 100, 2)
        if funnel_completion_rate < 20:
            alerts.append(
                {
                    "severity": "high",
                    "type": "funnel_completion",
                    "message": "Funnel completion is below 20%, indicating significant drop-off before conversion.",
                }
            )

    if session_change_pct <= -30:
        alerts.append(
            {
                "severity": "high",
                "type": "session_drop",
                "message": f"Sessions dropped {abs(session_change_pct)}% in the last 5 minutes versus the previous window.",
            }
        )
    if conversion_change_pct <= -30:
        alerts.append(
            {
                "severity": "high",
                "type": "conversion_drop",
                "message": f"Conversion sessions dropped {abs(conversion_change_pct)}% in the last 5 minutes.",
            }
        )
    if conversion_change_pct >= 40:
        alerts.append(
            {
                "severity": "info",
                "type": "conversion_spike",
                "message": f"Conversion sessions increased {conversion_change_pct}% in the last 5 minutes.",
            }
        )

    summary = {
        "kpis": {
            "events": total_events,
            "users": len(unique_users),
            "sessions": len(unique_sessions),
            "events_per_session": round((total_events / len(unique_sessions)), 2) if unique_sessions else 0.0,
            "conversion_events": len(conversion_events),
            "hero_views": len(hero_views),
            "scroll_events": len(scroll_events),
        },
    }

    booking_eligible_users = {
        item["user_id"]
        for item in events
        if item["user_id"]
        and item.get("page") == "juridisk-konsultation"
        and item["action"] == "page_view"
    }
    booked_users = {item["user_id"] for item in conversion_events if item["user_id"]}
    booked_sessions = {item["session_id"] for item in conversion_events if item["session_id"]}

    summary["kpis"]["book_appointment_cvr_pct"] = round(
        (len(booked_users) / len(booking_eligible_users)) * 100, 2
    ) if booking_eligible_users else 0.0
    summary["kpis"]["session_conversion_rate_pct"] = round(
        (len(booked_sessions) / len(unique_sessions)) * 100, 2
    ) if unique_sessions else 0.0

    summary.update({
        "funnel": funnel,
        "drop_offs": drop_offs,
        "channels": channels,
        "cohorts": cohorts,
        "cohort_retention": cohort_retention,
        "insights": {
            "refresh_seconds": 5,
            "trends": [
                {
                    "metric": "users",
                    "direction": user_trend,
                    "change_pct": user_change_pct,
                    "previous_window": len(previous_users),
                    "current_window": len(recent_users),
                },
                {
                    "metric": "sessions",
                    "direction": session_trend,
                    "change_pct": session_change_pct,
                    "previous_window": len(previous_sessions),
                    "current_window": len(recent_sessions),
                },
                {
                    "metric": "conversion_sessions",
                    "direction": conversion_trend,
                    "change_pct": conversion_change_pct,
                    "previous_window": len(previous_conversion_sessions),
                    "current_window": len(recent_conversion_sessions),
                },
            ],
            "alerts": alerts,
        },
        "top_targets": [{"target": target, "conversions": count} for target, count in top_targets.most_common(10)],
        "engagement_timeseries": engagement_timeseries,
    })
    return _cors_json(summary)


@csrf_exempt
def simulate_traffic(request):
    if request.method == "OPTIONS":
        return _cors_json({"status": "ok"})
    if request.method != "POST":
        return _cors_json({"error": "invalid request"}, status=400)

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _cors_json({"error": "invalid json"}, status=400)

    if (data.get("password") or "").strip() != SIMULATION_PASSWORD:
        return _cors_json({"error": "unauthorized"}, status=403)

    result = run_simulation_to_db(
        users=data.get("users", 40),
        min_sessions=data.get("min_sessions", 1),
        max_sessions=data.get("max_sessions", 3),
        seed=data.get("seed"),
    )
    return _cors_json({"status": "ok", **result})
