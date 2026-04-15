import json
from collections import Counter, defaultdict
from ipaddress import ip_address

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Event

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

    Event.objects.create(
        page=page,
        step=(data.get("step") or "").strip(),
        section=(data.get("section") or "").strip(),
        action=action,
        service=(data.get("service") or "").strip(),
        target=(data.get("target") or "").strip()[:255],
        session_id=(data.get("session_id") or "").strip(),
        url=(data.get("url") or "").strip(),
        referrer=(data.get("referrer") or "").strip(),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        ip_address=_client_ip(request),
        metadata=data,
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
            "session_id",
            "action",
            "target",
            "metadata",
        )
    )

    total_events = len(events)
    unique_sessions = {item["session_id"] for item in events if item["session_id"]}

    conversion_actions = {
        "primary_navigation_click",
        "module_click",
        "click_cta",
        "service_card_click",
        "nav_anchor",
        "nav_service",
        "nav_home",
        "nav_hub",
        "nav_website",
        "return_hub",
        "footer_link_click",
        "cross_sell_click",
    }
    conversion_events = [item for item in events if item["action"] in conversion_actions]
    hero_views = [
        item
        for item in events
        if item["action"] == "section_view" and (item.get("section") or "").strip() == "hero"
    ]
    scroll_events = [item for item in events if item["action"] == "scroll_depth"]

    funnel_actions = [
        ("Landing", "page_view"),
        ("Hero Viewed", "hero_view"),
        ("Scroll 50%", "scroll_depth"),
        ("Subpage Click", "subpage_click"),
        ("Primary CTA", "primary_navigation_click"),
    ]

    funnel = []
    for label, action_name in funnel_actions:
        sessions_for_action = set()
        for item in events:
            if action_name == "hero_view":
                if item["action"] != "section_view" or (item.get("section") or "").strip() != "hero":
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

    channel_sessions = defaultdict(set)
    channel_events = Counter()
    channel_conversions = Counter()

    for item in events:
        metadata = item.get("metadata") or {}
        channel = (metadata.get("source_channel") or "unknown").strip() or "unknown"
        if item["session_id"]:
            channel_sessions[channel].add(item["session_id"])
        channel_events[channel] += 1
        if item["action"] in conversion_actions:
            channel_conversions[channel] += 1

    channels = []
    for channel in sorted(channel_events.keys()):
        session_count = len(channel_sessions[channel])
        conversions = channel_conversions[channel]
        channels.append(
            {
                "channel": channel,
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

    top_targets = Counter()
    for item in conversion_events:
        target = item.get("target") or "(no target)"
        top_targets[target] += 1

    summary = {
        "kpis": {
            "events": total_events,
            "sessions": len(unique_sessions),
            "conversion_events": len(conversion_events),
            "hero_views": len(hero_views),
            "scroll_events": len(scroll_events),
            "session_conversion_rate_pct": round(
                (len({item["session_id"] for item in conversion_events if item["session_id"]}) / len(unique_sessions)) * 100,
                2,
            )
            if unique_sessions
            else 0.0,
        },
        "funnel": funnel,
        "channels": channels,
        "cohorts": cohorts,
        "top_targets": [{"target": target, "conversions": count} for target, count in top_targets.most_common(10)],
    }
    return _cors_json(summary)
