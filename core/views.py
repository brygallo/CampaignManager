"""Generic views: home dashboard, Select2 AutoResponse, error pages."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django_select2.views import AutoResponseView as BaseAutoResponseView


class AutoResponseView(BaseAutoResponseView):
    """Handle Select2 dependent-field requests and multi-value queries."""

    def get_queryset(self):
        return super().get_queryset()


@login_required
def home(request):
    """Dashboard landing page with summary cards for the active Site."""
    context = {
        "breadcrumbs": [("Inicio", None)],
    }
    return render(request, "home.html", context)


def error_403(request, exception=None):
    return render(request, "errors/403.html", status=403)


def error_404(request, exception=None):
    return render(request, "errors/404.html", status=404)


def error_500(request):
    return render(request, "errors/500.html", status=500)
