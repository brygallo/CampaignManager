"""URL configuration for CampaignManager."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

import superadmin

from . import views as core_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", core_views.home, name="home"),
    path("admin-panel/", core_views.SuperAdminLandingView.as_view(), name="superadmin_home"),
    path("", include("apps.authentication.urls")),
    path("", include("apps.insoles.urls")),
    path("", include("apps.workflows.urls")),
    path("select2/", include("core.select2")),
    path("inbox/notifications/", include("notifications.urls", namespace="notifications")),
    path("api/v1/", include("api.urls")),
    # Superadmin (generic CRUD) must come last because it captures "<app>/<model>/..." patterns.
    path("", superadmin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=settings.STATICFILES_DIRS[0]
        if settings.STATICFILES_DIRS
        else settings.STATIC_ROOT,
    )

handler403 = "core.views.error_403"
handler404 = "core.views.error_404"
handler500 = "core.views.error_500"
