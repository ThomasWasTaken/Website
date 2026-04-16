from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse


PAGES_DIR = settings.BASE_DIR.parent.parent / "assets" / "pages"
SITE_ROOT = settings.BASE_DIR.parent.parent

ALLOWED_FILES = {
    "legal_site.html": "text/html; charset=utf-8",
    "legal_site_agentveiw.html": "text/html; charset=utf-8",
    "index.html": "text/html; charset=utf-8",
    "saas-analytics.html": "text/html; charset=utf-8",
    "testamente.html": "text/html; charset=utf-8",
    "ægtepagt.html": "text/html; charset=utf-8",
    "samejeoverenskomst.html": "text/html; charset=utf-8",
    "fuldmagt.html": "text/html; charset=utf-8",
    "juridisk-konsultation.html": "text/html; charset=utf-8",
    "lejekontrakt.html": "text/html; charset=utf-8",
    "legal-agent-shared.css": "text/css; charset=utf-8",
    "legal-agent-shared.js": "application/javascript; charset=utf-8",
}


def serve_legal_file(request, filename="legal_site_agentveiw.html"):
    if filename not in ALLOWED_FILES:
        raise Http404("Page not found")

    file_path = PAGES_DIR / filename
    if not file_path.exists():
        raise Http404("Page not found")

    return HttpResponse(file_path.read_text(encoding="utf-8"), content_type=ALLOWED_FILES[filename])


ROOT_FILES = {
    "index.html": "text/html; charset=utf-8",
    "index_light.html": "text/html; charset=utf-8",
    "index_light copy.html": "text/html; charset=utf-8",
}


def serve_frontpage(request):
    return serve_root_file(request, "index_light.html")


def serve_root_file(request, filename):
    if filename not in ROOT_FILES:
        raise Http404("Page not found")

    file_path = SITE_ROOT / filename
    if not file_path.exists():
        raise Http404("Page not found")

    return HttpResponse(file_path.read_text(encoding="utf-8"), content_type=ROOT_FILES[filename])


def serve_assets_page_file(request, filename):
    if filename not in ALLOWED_FILES:
        raise Http404("Page not found")
    return serve_legal_file(request, filename)
