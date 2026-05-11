"""API REST v1.

Versioning is path-based: `/api/v1/...`. Add new endpoints to ``router``
or to ``v1_extra_patterns`` below. Schema and Swagger UI are mounted at
``/api/v1/schema/`` and ``/api/v1/docs/``; both require authentication because
they reflect the full surface of the (still tenant-scoped) API.
"""
from django.urls import include, path
from django.views.generic.base import RedirectView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
# Register ViewSets here as the API grows. Example:
# router.register(r"campaigns", CampaignViewSet, basename="campaign")

v1_extra_patterns: list = []

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="api_docs", permanent=False)),
    path("schema/", SpectacularAPIView.as_view(), name="api_schema"),
    path(
        "docs/",
        SpectacularSwaggerView.as_view(url_name="api_schema"),
        name="api_docs",
    ),
    path("", include((router.urls + v1_extra_patterns, "v1"), namespace="v1")),
]
