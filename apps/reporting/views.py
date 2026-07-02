from django.http import JsonResponse
from django.views.generic import View

from .exporters import export_report, supported_export_formats


class ReportExportView(View):
    file_format = "csv"

    def get_report(self):
        raise NotImplementedError

    def get_file_format(self):
        return self.kwargs.get("file_format") or self.file_format

    def get(self, request, *args, **kwargs):
        file_format = self.get_file_format()
        if file_format not in supported_export_formats():
            return JsonResponse({"error": "Formato de exportación no válido."}, status=400)
        return export_report(self.get_report(), file_format)
