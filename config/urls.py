from django.contrib import admin
from django.urls import path, include, re_path
from django.http import HttpResponse
from django.conf import settings
import os


def serve_react_app(request):
    """
    Catch-all view that serves the React SPA's index.html.
    WhiteNoise handles the static assets (JS/CSS/images).
    This view handles client-side routes like /dashboard, /ingest, etc.
    """
    # Look for index.html in the React build output
    react_index = os.path.join(settings.BASE_DIR, "frontend", "dist", "index.html")
    if os.path.exists(react_index):
        with open(react_index, "r") as f:
            return HttpResponse(f.read(), content_type="text/html")
    
    # Fallback: if no React build exists (dev mode), show a message
    return HttpResponse(
        "<h1>Breathe ESG API</h1>"
        "<p>Frontend not built. Run <code>cd frontend && npm run build</code> first, "
        "or use <code>npm run dev</code> on port 5173 for development.</p>",
        content_type="text/html",
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("emissions.urls")),
    # SPA catch-all: serve React index.html for all non-API, non-admin routes
    re_path(r"^(?!api/|admin/).*$", serve_react_app, name="react-app"),
]
