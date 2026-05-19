"""URL configuration for CampaignManager."""
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path, re_path

import superadmin

from . import views as core_views

urlpatterns = [
    path("", core_views.inicio, name="home"),
    path("admin-panel/", core_views.home, name="superadmin_home"),
    # Authenticated, tenant-scoped media serving. Replaces Django's default
    # static media handler so tenant A cannot read tenant B's uploads by
    # guessing the URL.
    re_path(
        rf"^{settings.MEDIA_URL.lstrip('/')}(?P<path>.*)$",
        core_views.serve_protected_media,
        name="protected_media",
    ),
    path("", include("apps.authentication.urls")),
    path("", include("apps.campaigns.urls")),
    path("", include("apps.insoles.urls")),
    path("", include("apps.workflows.urls")),
    path("", include("apps.field_surveys.urls")),
    path("", include("apps.territorial_ads.urls")),
    path("", include("apps.political_agenda.urls")),
    path("", include("apps.tenancy.urls")),
    path("select2/", include("core.select2")),
    path("inbox/notifications/", include("notifications.urls", namespace="notifications")),
    path("api/v1/", include("api.urls")),
    # Superadmin (generic CRUD) must come last because it captures "<app>/<model>/..." patterns.
    path("", superadmin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=settings.STATICFILES_DIRS[0]
        if settings.STATICFILES_DIRS
        else settings.STATIC_ROOT,
    )
    # Preview routes for the custom error pages. In DEBUG=True Django bypasses
    # `handler404`/`handler500` and shows its own technical error page, so the
    # only way to validate the templates pre-deploy is to route to them
    # explicitly.
    urlpatterns += [
        path("_dev/errors/403/", core_views.error_403),
        path("_dev/errors/404/", core_views.error_404),
        path("_dev/errors/500/", core_views.error_500),
    ]

handler403 = "core.views.error_403"
handler404 = "core.views.error_404"
handler500 = "core.views.error_500"
