"""Generic views: home dashboard, Select2 AutoResponse, error pages."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django_select2.views import AutoResponseView as BaseAutoResponseView


class AutoResponseView(BaseAutoResponseView):
    """Handle Select2 dependent-field requests and multi-value queries."""

    def get_queryset(self):
        for key, value in self.request.GET.items():
            if key == "field_id":
                continue
            key_tuple = key.split("-")
            if len(key_tuple) == 3:
                self.widget.dependent_fields.update({key: key_tuple[2]})

        kwargs = {
            model_field_name: self.request.GET.get(form_field_name)
            for form_field_name, model_field_name in self.widget.dependent_fields.items()
            if form_field_name in self.request.GET
            and self.request.GET.get(form_field_name, "") != ""
        }
        kwargs.update(
            {
                f"{model_field_name}__in": self.request.GET.getlist(
                    f"{form_field_name}[]", []
                )
                for form_field_name, model_field_name in self.widget.dependent_fields.items()
            }
        )
        return self.widget.filter_queryset(
            self.request,
            self.term,
            self.queryset,
            **{key: value for key, value in kwargs.items() if value},
        )


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
