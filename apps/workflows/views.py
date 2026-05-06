# Django
from django.apps import apps
from django.db import transaction
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.generic import View

# Libraries
from django_fsm import has_transition_perm

# Local
from superadmin.utils import import_class

from .exceptions import WorkflowException


class ChangeStateView(View):
    http_method_names = ["get", "post"]

    def get(self, request, *args, **kwargs):
        """Method get view"""
        try:
            transition_name = request.GET.get("transition")
            object = self.get_object()

            if not hasattr(object, transition_name):
                message = "La transición %s no existe." % transition_name
                return self.error(message)

            transition = getattr(object, transition_name)
            if not has_transition_perm(transition, request.user):
                return self.error("No tiene los permisos para realizar esta acción.")

            transition_method = self.get_transition(object, transition_name)
            form_class = self.get_form(transition_method)
            if form_class:
                template = render_to_string(
                    "workflows/form.html",
                    context={"form": form_class(**self.get_kwargs_form())},
                )
                response = {"template": template}
                return JsonResponse(response, status=200)
            return self.error(
                "No se pudo encontrar el formulario para esta transición."
            )
        except WorkflowException as e:
            return self.error(str(e))

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        with transaction.atomic():
            try:

                transition_name = request.POST.get("transition")
                object = self.get_object()

                if not hasattr(object, transition_name):
                    message = "La transición %s no existe." % transition_name
                    return self.error(message)

                transition = getattr(object, transition_name)
                if not has_transition_perm(transition, request.user):
                    return self.error(
                        "No tiene los permisos para realizar esta acción."
                    )

                transition_method = self.get_transition(object, transition_name)
                form_class = self.get_form(transition_method)
                if form_class:
                    form = form_class(**self.get_kwargs_form())
                    if not form.is_valid():
                        template = render_to_string(
                            "workflows/form.html",
                            context={"form": form},
                        )
                        return JsonResponse(
                            {
                                "template": template,
                                "form_invalid": True,
                                "error": "Revisa los campos marcados.",
                            },
                            status=400,
                        )
                response = transition(**self.get_kwargs())
                if response:
                    return response
                object.save()
                return self.success("La acción ha sido realizada con éxito.")
            except WorkflowException as e:
                transaction.set_rollback(True)
                return self.error(str(e))

    def get_kwargs(self):
        kwargs = {"user": self.request.user}
        if self.request.FILES:
            keys = self.request.FILES.keys()
            for key in keys:
                value = self.request.FILES.get(str(key))
                kwargs.update({key: value})
        if self.request.POST:
            keys = self.request.POST.keys()
            for key in keys:
                value = self.request.POST.getlist(str(key))
                if not (len(value) > 1):
                    value = self.request.POST.get(str(key))
                kwargs.update({key: value})
        return kwargs

    def get_kwargs_form(self):
        kwargs = {}
        if self.request.method in ("POST", "PUT"):
            kwargs.update(
                {
                    "data": self.request.POST,
                    "files": self.request.FILES,
                }
            )
        return kwargs

    def get_object(self):
        app_name = self.kwargs.get("app")
        model_name = self.kwargs.get("model")
        pk = self.kwargs.get("pk")
        model_class = apps.get_model(app_name, model_name)
        object = model_class.objects.get(pk=pk)
        return object

    def get_transition(self, instance, transition_name):
        transition = getattr(instance, transition_name)
        transitions = transition._django_fsm.transitions
        transition = next(iter(list(transitions.values())), None)
        return transition

    def get_form(self, transition_method):
        form = transition_method.custom.get("form", None)
        if form:
            directories = form.split(".")
            form_class = directories.pop(-1)
            module = ".".join(directories)
            form = import_class(module, form_class)
        return form

    def success(self, message):
        response = {"message": message}
        return JsonResponse(response, status=200)

    def error(self, message):
        response = {"error": message}
        return JsonResponse(response, status=400)
