from django.contrib import admin
from django.urls import path, include

from .views import serve_legal_file, serve_frontpage, serve_root_file, serve_assets_page_file

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("tracking.urls")),
    path("", serve_frontpage, name="home"),
    path("index.html", serve_root_file, {"filename": "index.html"}, name="index"),
    path("index_light.html", serve_root_file, {"filename": "index_light.html"}, name="index-light"),
    path("assets/pages/<str:filename>", serve_assets_page_file, name="assets-pages"),
    path("testamente.html", serve_legal_file, {"filename": "testamente.html"}, name="testamente"),
    path("ægtepagt.html", serve_legal_file, {"filename": "ægtepagt.html"}, name="ægtepagt"),
    path("samejeoverenskomst.html", serve_legal_file, {"filename": "samejeoverenskomst.html"}, name="samejeoverenskomst"),
    path("fuldmagt.html", serve_legal_file, {"filename": "fuldmagt.html"}, name="fuldmagt"),
    path("juridisk-konsultation.html", serve_legal_file, {"filename": "juridisk-konsultation.html"}, name="juridisk-konsultation"),
    path("lejekontrakt.html", serve_legal_file, {"filename": "lejekontrakt.html"}, name="lejekontrakt"),
    path("legal-agent-shared.css", serve_legal_file, {"filename": "legal-agent-shared.css"}, name="legal-agent-shared-css"),
    path("legal-agent-shared.js", serve_legal_file, {"filename": "legal-agent-shared.js"}, name="legal-agent-shared-js"),
]
