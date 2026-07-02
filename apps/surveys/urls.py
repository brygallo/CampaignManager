from django.urls import path

from . import views

app_name = "surveys"

urlpatterns = [
    path("encuestas/aplicar/", views.SurveyApplyListView.as_view(), name="apply_list"),
    path("encuestas/<int:pk>/constructor/", views.SurveyBuilderView.as_view(), name="builder"),
    path(
        "encuestas/<int:pk>/constructor/pregunta/",
        views.SurveyBuilderQuestionInsoleView.as_view(),
        name="builder_question_modal",
    ),
    path(
        "encuestas/<int:pk>/constructor/pregunta/<int:question_pk>/",
        views.SurveyBuilderQuestionEditInsoleView.as_view(),
        name="builder_question_edit_modal",
    ),
    path(
        "encuestas/<int:pk>/constructor/seccion/",
        views.SurveyBuilderSectionInsoleView.as_view(),
        name="builder_section_modal",
    ),
    path(
        "encuestas/<int:pk>/constructor/seccion/<int:section_pk>/",
        views.SurveyBuilderSectionEditInsoleView.as_view(),
        name="builder_section_edit_modal",
    ),
    path(
        "encuestas/<int:pk>/constructor/ordenar/",
        views.SurveyBuilderReorderView.as_view(),
        name="builder_reorder",
    ),
    path("encuestas/<slug:slug>/responder/", views.SurveyRespondView.as_view(), name="respond"),
    path("encuestas/<slug:slug>/gracias/", views.SurveyThanksView.as_view(), name="thanks"),
    path("encuestas/<int:pk>/resultados/", views.SurveyResultsView.as_view(), name="results"),
    path("encuestas/<int:pk>/exportar.csv", views.SurveyExportCsvView.as_view(), name="export_csv"),
]
