import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.campaigns.models import Campaign, Candidate, Election, PoliticalMovement, Position
from apps.field_surveys.models import (
    AdvertisingType,
    Competitor,
    CompetitorAdvertisingDetection,
    FieldSurvey,
    SurveyAdvertisingResponse,
    SurveySupportLevel,
)
from apps.field_surveys.views import (
    DEFAULT_VISIT_COLOR,
    BrigadierAutoAssignMixin,
    CompetitorDetectionOwnershipMixin,
    FieldSurveyDashboardView,
    FieldSurveyDashboardHeatmapDataView,
    FieldSurveyFilterMixin,
    FieldSurveyMapDataView,
    FieldSurveyMapView,
    FieldSurveyOwnershipMixin,
    advertising_color,
    build_advertising_distribution,
    build_competitor_breakdown,
    build_support_distribution,
    build_visits_trend,
    can_view_all_field_surveys,
    competitor_detection_detail_url,
    fieldsurvey_detail_url,
    fieldsurvey_list_url,
    get_filter_context,
    support_color,
)


def _make_campaign(name):
    election = Election.objects.create(name=f"E {name}")
    candidate = Candidate.objects.create(full_name=f"C {name}")
    movement = PoliticalMovement.objects.create(name=f"M {name}")
    position = Position.objects.create(name=f"P {name}")
    return Campaign.objects.create(
        name=name,
        election=election,
        candidate=candidate,
        movement=movement,
        position=position,
    )


class _BaseQsView:
    def get_queryset(self):
        return self.qs


class _OwnedFieldSurveyView(FieldSurveyOwnershipMixin, _BaseQsView):
    pass


class _OwnedCompetitorView(CompetitorDetectionOwnershipMixin, _BaseQsView):
    pass


class _BaseValidView:
    def form_valid(self, form):
        self.form = form
        return "ok"


class _AutoAssignView(BrigadierAutoAssignMixin, _BaseValidView):
    pass


class _FilterMixinView(FieldSurveyFilterMixin):
    def __init__(self, request):
        self.request = request


class FieldSurveyViewHelperTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        User = get_user_model()
        self.user = User.objects.create_user(username="fs1", email="fs1@example.com", password="x")
        self.staff = User.objects.create_user(
            username="fs2",
            email="fs2@example.com",
            password="x",
            is_staff=True,
        )
        self.user.user_permissions.add(Permission.objects.get(codename="view_fieldsurvey"))
        self.campaign = _make_campaign("A")
        self.level = SurveySupportLevel.objects.create(
            code="APOYA",
            name="Apoya",
            color="",
        )
        self.response = SurveyAdvertisingResponse.objects.create(
            code="ACEPTA",
            name="Acepta",
            color="",
        )
        self.ad_type = AdvertisingType.objects.create(code="A1", name="Tipo", icon="picture")

    def test_can_view_all_field_surveys_for_staff(self):
        self.assertTrue(can_view_all_field_surveys(self.staff))
        self.assertFalse(can_view_all_field_surveys(self.user))

    def test_support_and_advertising_color_use_fallbacks(self):
        self.assertEqual(support_color(None), DEFAULT_VISIT_COLOR)
        self.assertEqual(support_color(self.level), "#50cd89")
        self.assertEqual(advertising_color(None), DEFAULT_VISIT_COLOR)
        self.assertEqual(advertising_color(self.response), "#3e97ff")

    def test_ownership_mixins_filter_non_privileged_users(self):
        other_user = get_user_model().objects.create_user(
            username="fs3", email="fs3@example.com", password="x"
        )
        survey = FieldSurvey.objects.create(
            campaign=self.campaign,
            brigadier=self.user,
            latitude=Decimal("-2.1"),
            longitude=Decimal("-79.9"),
            created_by=self.user,
        )
        FieldSurvey.objects.create(
            campaign=self.campaign,
            brigadier=other_user,
            latitude=Decimal("-2.0"),
            longitude=Decimal("-79.8"),
            created_by=other_user,
        )
        detection = CompetitorAdvertisingDetection.objects.create(
            campaign=self.campaign,
            competitor=Competitor.objects.create(
                campaign=self.campaign,
                list_number="1",
                political_organization="Org",
            ),
            brigadier=self.user,
            advertising_type=self.ad_type,
            latitude=Decimal("-2.2"),
            longitude=Decimal("-79.8"),
            created_by=self.user,
        )
        CompetitorAdvertisingDetection.objects.create(
            campaign=self.campaign,
            competitor=Competitor.objects.create(
                campaign=self.campaign,
                list_number="9",
                political_organization="Otra",
            ),
            brigadier=other_user,
            advertising_type=self.ad_type,
            latitude=Decimal("-2.4"),
            longitude=Decimal("-79.7"),
            created_by=other_user,
        )
        fs_view = _OwnedFieldSurveyView()
        fs_view.qs = FieldSurvey.objects.all()
        fs_view.request = SimpleNamespace(user=self.user)
        self.assertEqual(list(fs_view.get_queryset()), [survey])

        cd_view = _OwnedCompetitorView()
        cd_view.qs = CompetitorAdvertisingDetection.objects.all()
        cd_view.request = SimpleNamespace(user=self.user)
        self.assertEqual(list(cd_view.get_queryset()), [detection])

    def test_ownership_mixins_leave_queryset_open_for_staff(self):
        survey = FieldSurvey.objects.create(
            campaign=self.campaign,
            brigadier=self.user,
            latitude=Decimal("-2.1"),
            longitude=Decimal("-79.9"),
            created_by=self.user,
        )
        detection = CompetitorAdvertisingDetection.objects.create(
            campaign=self.campaign,
            competitor=Competitor.objects.create(
                campaign=self.campaign,
                list_number="4",
                political_organization="Org 4",
            ),
            brigadier=self.user,
            advertising_type=self.ad_type,
            latitude=Decimal("-2.2"),
            longitude=Decimal("-79.8"),
            created_by=self.user,
        )
        fs_view = _OwnedFieldSurveyView()
        fs_view.qs = FieldSurvey.objects.all()
        fs_view.request = SimpleNamespace(user=self.staff)
        self.assertEqual(list(fs_view.get_queryset()), [survey])

        cd_view = _OwnedCompetitorView()
        cd_view.qs = CompetitorAdvertisingDetection.objects.all()
        cd_view.request = SimpleNamespace(user=self.staff)
        self.assertEqual(list(cd_view.get_queryset()), [detection])

    def test_brigadier_auto_assign_mixin_sets_missing_fields(self):
        view = _AutoAssignView()
        view.request = SimpleNamespace(user=self.user)
        form = SimpleNamespace(instance=SimpleNamespace(brigadier_id=None, created_by_id=None))
        self.assertEqual(view.form_valid(form), "ok")
        self.assertEqual(form.instance.brigadier, self.user)
        self.assertEqual(form.instance.created_by, self.user)

    def test_brigadier_auto_assign_mixin_does_not_overwrite_existing_fields(self):
        other_user = get_user_model().objects.create_user(
            username="fs4", email="fs4@example.com", password="x"
        )
        view = _AutoAssignView()
        view.request = SimpleNamespace(user=self.user)
        form = SimpleNamespace(
            instance=SimpleNamespace(
                brigadier_id=other_user.pk,
                brigadier=other_user,
                created_by_id=other_user.pk,
                created_by=other_user,
            )
        )
        self.assertEqual(view.form_valid(form), "ok")
        self.assertEqual(form.instance.brigadier, other_user)
        self.assertEqual(form.instance.created_by, other_user)

    def test_url_helpers_reverse_expected_routes(self):
        survey = FieldSurvey.objects.create(
            campaign=self.campaign,
            brigadier=self.user,
            latitude=Decimal("-2.1"),
            longitude=Decimal("-79.9"),
            created_by=self.user,
        )
        detection = CompetitorAdvertisingDetection.objects.create(
            campaign=self.campaign,
            competitor=Competitor.objects.create(
                campaign=self.campaign,
                list_number="5",
                political_organization="Org 5",
            ),
            brigadier=self.user,
            advertising_type=self.ad_type,
            latitude=Decimal("-2.2"),
            longitude=Decimal("-79.8"),
            created_by=self.user,
        )
        self.assertIn("field_surveys", fieldsurvey_list_url())
        self.assertIn(str(survey.pk), fieldsurvey_detail_url(survey.pk))
        self.assertIn(str(detection.pk), competitor_detection_detail_url(detection.pk))

    def test_filter_mixin_applies_all_optional_filters(self):
        privileged = get_user_model().objects.create_user(
            username="fs5",
            email="fs5@example.com",
            password="x",
            is_staff=True,
        )
        other_user = get_user_model().objects.create_user(
            username="fs6", email="fs6@example.com", password="x"
        )
        level_other = SurveySupportLevel.objects.create(code="NO_APOYA", name="No apoya")
        response_other = SurveyAdvertisingResponse.objects.create(code="RECHAZA", name="Rechaza")
        target = FieldSurvey.objects.create(
            campaign=self.campaign,
            brigadier=self.user,
            latitude=Decimal("-2.10"),
            longitude=Decimal("-79.91"),
            support_level=self.level,
            advertising_response=self.response,
            created_by=self.user,
        )
        FieldSurvey.objects.filter(pk=target.pk).update(created_date="2026-01-03T10:00:00Z")
        FieldSurvey.objects.create(
            campaign=self.campaign,
            brigadier=other_user,
            latitude=Decimal("-2.11"),
            longitude=Decimal("-79.92"),
            support_level=level_other,
            advertising_response=response_other,
            created_by=other_user,
        )
        request = self.factory.get(
            "/",
            {
                "campaign": self.campaign.pk,
                "brigadier": self.user.pk,
                "support_level": self.level.pk,
                "advertising_response": self.response.pk,
                "date_from": "2026-01-02",
                "date_to": "2026-01-04",
            },
        )
        request.user = privileged
        request.active_campaign = None
        filtered = _FilterMixinView(request).apply_filters(FieldSurvey.objects.all())
        self.assertEqual(list(filtered), [target])

    def test_distribution_and_trend_helpers_cover_fallback_paths(self):
        data = build_support_distribution({})
        self.assertEqual(data[0]["value"], 0)
        ads = build_advertising_distribution({})
        self.assertEqual(ads[0]["value"], 0)

        survey = FieldSurvey.objects.create(
            campaign=self.campaign,
            brigadier=self.user,
            latitude=Decimal("-2.1"),
            longitude=Decimal("-79.9"),
            created_by=self.user,
        )
        request = self.factory.get("/", {"date_from": "bad-date", "date_to": "2026-01-01"})
        trend = build_visits_trend(request, FieldSurvey.objects.filter(pk=survey.pk))
        self.assertTrue(trend["labels"])
        reverse_request = self.factory.get("/", {"date_from": "2026-01-05", "date_to": "2026-01-01"})
        reversed_trend = build_visits_trend(reverse_request, FieldSurvey.objects.filter(pk=survey.pk))
        self.assertEqual(len(reversed_trend["labels"]), 5)

    def test_competitor_breakdown_uses_default_color_and_label(self):
        competitor = Competitor.objects.create(
            campaign=self.campaign,
            list_number="2",
            political_organization="",
            color="",
        )
        CompetitorAdvertisingDetection.objects.create(
            campaign=self.campaign,
            competitor=competitor,
            brigadier=self.user,
            advertising_type=self.ad_type,
            latitude=Decimal("-2.3"),
            longitude=Decimal("-79.7"),
            created_by=self.user,
        )
        rows = build_competitor_breakdown(CompetitorAdvertisingDetection.objects.all())
        self.assertEqual(rows[0]["label"], "—")
        self.assertEqual(rows[0]["color"], "#d9214e")

    def test_heatmap_view_returns_layers_and_skips_null_points(self):
        indeciso = SurveySupportLevel.objects.create(code="INDECISO", name="Indeciso")
        survey = FieldSurvey.objects.create(
            campaign=self.campaign,
            brigadier=self.user,
            latitude=Decimal("-2.11"),
            longitude=Decimal("-79.91"),
            support_level=self.level,
            voters_count=4,
            created_by=self.user,
        )
        FieldSurvey.objects.create(
            campaign=self.campaign,
            brigadier=self.user,
            latitude=Decimal("-2.12"),
            longitude=Decimal("-79.92"),
            support_level=indeciso,
            voters_count=0,
            created_by=self.user,
        )
        competitor = Competitor.objects.create(
            campaign=self.campaign,
            list_number="3",
            political_organization="Org 3",
        )
        CompetitorAdvertisingDetection.objects.create(
            campaign=self.campaign,
            competitor=competitor,
            brigadier=self.user,
            advertising_type=self.ad_type,
            latitude=Decimal("-2.13"),
            longitude=Decimal("-79.93"),
            field_survey=survey,
            created_by=self.user,
        )
        request = self.factory.get("/")
        request.user = self.user
        request.active_campaign = self.campaign
        response = FieldSurveyDashboardHeatmapDataView.as_view()(request)
        payload = json.loads(response.content)
        self.assertEqual(payload["count"], 3)
        self.assertEqual(payload["layers"]["apoyo"]["count"], 1)
        self.assertEqual(payload["layers"]["indecisos"]["count"], 1)
        self.assertEqual(payload["layers"]["competencia"]["count"], 1)

    def test_heatmap_view_for_staff_keeps_all_competitor_ads(self):
        self.staff.user_permissions.add(Permission.objects.get(codename="view_fieldsurvey"))
        indeciso = SurveySupportLevel.objects.create(code="INDECISO", name="Indeciso 2")
        survey = FieldSurvey.objects.create(
            campaign=self.campaign,
            brigadier=self.user,
            latitude=Decimal("-2.11"),
            longitude=Decimal("-79.91"),
            support_level=self.level,
            voters_count=2,
            created_by=self.user,
        )
        FieldSurvey.objects.create(
            campaign=self.campaign,
            brigadier=self.staff,
            latitude=Decimal("-2.12"),
            longitude=Decimal("-79.92"),
            support_level=indeciso,
            voters_count=1,
            created_by=self.staff,
        )
        competitor = Competitor.objects.create(
            campaign=self.campaign,
            list_number="7",
            political_organization="Org 7",
        )
        CompetitorAdvertisingDetection.objects.create(
            campaign=self.campaign,
            competitor=competitor,
            brigadier=self.staff,
            advertising_type=self.ad_type,
            latitude=Decimal("-2.13"),
            longitude=Decimal("-79.93"),
            field_survey=survey,
            created_by=self.staff,
        )
        request = self.factory.get("/")
        request.user = self.staff
        request.active_campaign = self.campaign
        response = FieldSurveyDashboardHeatmapDataView.as_view()(request)
        payload = json.loads(response.content)
        self.assertEqual(payload["layers"]["competencia"]["count"], 1)
        self.assertEqual(payload["count"], 3)

    def test_heatmap_helpers_skip_null_coordinates_in_internal_loops(self):
        class FakeSurveyRows:
            def values_list(self, *args, **kwargs):
                return self

            def distinct(self):
                return [(None, Decimal("-79.90"), 3), (Decimal("-2.10"), Decimal("-79.91"), 2)]

        class FakeSurveyQs:
            def filter(self, **kwargs):
                return FakeSurveyRows()

        view = FieldSurveyDashboardHeatmapDataView()
        points = view._survey_points(FakeSurveyQs(), "APOYA")
        self.assertEqual(points, [[-2.1, -79.91, 2.0]])

        class FakeCompetitorAds:
            def values_list(self, *args, **kwargs):
                return [(None, Decimal("-79.80")), (Decimal("-2.20"), Decimal("-79.81"))]

        request = self.factory.get("/")
        request.user = self.staff
        request.active_campaign = self.campaign
        class EmptySurveyRows:
            def values_list(self, *args, **kwargs):
                return self

            def distinct(self):
                return []

        class EmptySurveyQs:
            def filter(self, **kwargs):
                return EmptySurveyRows()

        with patch.object(
            FieldSurveyDashboardHeatmapDataView,
            "filtered_queryset",
            return_value=EmptySurveyQs(),
        ):
            with patch(
                "apps.field_surveys.views.CompetitorAdvertisingDetection.objects.filter",
                return_value=FakeCompetitorAds(),
            ):
                response = FieldSurveyDashboardHeatmapDataView.as_view()(request)
        payload = json.loads(response.content)
        self.assertEqual(payload["layers"]["competencia"]["count"], 1)

    def test_map_data_applies_optional_filters_and_exposes_edit_urls_for_staff(self):
        self.staff.user_permissions.add(Permission.objects.get(codename="view_fieldsurvey"))
        self.staff.user_permissions.add(
            Permission.objects.get(codename="change_fieldsurvey")
        )
        self.staff.user_permissions.add(
            Permission.objects.get(codename="delete_fieldsurvey")
        )
        self.staff.user_permissions.add(
            Permission.objects.get(codename="change_competitoradvertisingdetection")
        )
        self.staff.user_permissions.add(
            Permission.objects.get(codename="delete_competitoradvertisingdetection")
        )
        competitor = Competitor.objects.create(
            campaign=self.campaign,
            list_number="8",
            political_organization="Org 8",
        )
        survey = FieldSurvey.objects.create(
            campaign=self.campaign,
            brigadier=self.staff,
            latitude=Decimal("-2.20"),
            longitude=Decimal("-79.95"),
            support_level=self.level,
            advertising_response=self.response,
            created_by=self.staff,
        )
        FieldSurvey.objects.filter(pk=survey.pk).update(created_date="2026-01-03T10:00:00Z")
        ad = CompetitorAdvertisingDetection.objects.create(
            campaign=self.campaign,
            competitor=competitor,
            brigadier=self.staff,
            advertising_type=self.ad_type,
            latitude=Decimal("-2.21"),
            longitude=Decimal("-79.96"),
            created_by=self.staff,
        )
        CompetitorAdvertisingDetection.objects.filter(pk=ad.pk).update(
            created_date="2026-01-03T10:00:00Z"
        )
        request = self.factory.get(
            "/",
            {
                "campaign": self.campaign.pk,
                "competitor": competitor.pk,
                "date_from": "2026-01-02",
                "date_to": "2026-01-04",
            },
        )
        request.user = self.staff
        request.active_campaign = None
        response = FieldSurveyMapDataView.as_view()(request)
        payload = json.loads(response.content)
        self.assertIn("update_url", payload["visits"][0])
        self.assertIn("delete_url", payload["visits"][0])
        self.assertIn("update_url", payload["competitor_ads"][0])
        self.assertIn("delete_url", payload["competitor_ads"][0])

    def test_dashboard_for_staff_skips_brigadier_filter(self):
        self.staff.user_permissions.add(Permission.objects.get(codename="view_fieldsurvey"))
        other_user = get_user_model().objects.create_user(
            username="fs7", email="fs7@example.com", password="x"
        )
        FieldSurvey.objects.create(
            campaign=self.campaign,
            brigadier=self.user,
            latitude=Decimal("-2.31"),
            longitude=Decimal("-79.97"),
            created_by=self.user,
        )
        FieldSurvey.objects.create(
            campaign=self.campaign,
            brigadier=other_user,
            latitude=Decimal("-2.32"),
            longitude=Decimal("-79.98"),
            created_by=other_user,
        )
        request = self.factory.get("/")
        request.user = self.staff
        request.active_campaign = self.campaign
        response = FieldSurveyDashboardView.as_view()(request)
        self.assertEqual(response.context_data["metrics"]["total_visits"], 2)

    def test_map_data_without_active_campaign_keeps_all_competitors_and_truncates(self):
        self.staff.user_permissions.add(Permission.objects.get(codename="view_fieldsurvey"))
        competitor = Competitor.objects.create(
            campaign=self.campaign,
            list_number="10",
            political_organization="Org 10",
        )
        for idx in range(2):
            FieldSurvey.objects.create(
                campaign=self.campaign,
                brigadier=self.staff,
                latitude=Decimal(f"-2.4{idx}"),
                longitude=Decimal(f"-79.8{idx}"),
                support_level=self.level,
                created_by=self.staff,
            )
        CompetitorAdvertisingDetection.objects.create(
            campaign=self.campaign,
            competitor=competitor,
            brigadier=self.staff,
            advertising_type=self.ad_type,
            latitude=Decimal("-2.50"),
            longitude=Decimal("-79.70"),
            created_by=self.staff,
        )
        original = FieldSurveyMapDataView.MAX_POINTS
        FieldSurveyMapDataView.MAX_POINTS = 2
        try:
            request = self.factory.get("/")
            request.user = self.staff
            request.active_campaign = None
            response = FieldSurveyMapDataView.as_view()(request)
        finally:
            FieldSurveyMapDataView.MAX_POINTS = original
        payload = json.loads(response.content)
        self.assertTrue(payload["truncated"])
        self.assertEqual(payload["returned"], 2)

    def test_map_view_filter_context_for_staff_includes_active_campaign(self):
        other_campaign = _make_campaign("B")
        request = self.factory.get("/")
        request.user = self.staff
        request.active_campaign = other_campaign
        context = get_filter_context(request)
        self.assertEqual(context["active_campaign_filter_id"], str(other_campaign.pk))
        self.assertEqual({campaign.pk for campaign in context["filter_campaigns"]}, {self.campaign.pk, other_campaign.pk})

    def test_filter_context_hides_inactive_campaigns_without_history_permission(self):
        inactive = _make_campaign("Inactiva")
        inactive.is_active = False
        inactive.save(update_fields=["is_active"])
        request = self.factory.get("/")
        request.user = self.staff
        request.active_campaign = None
        context = get_filter_context(request)
        self.assertNotIn(inactive.pk, {campaign.pk for campaign in context["filter_campaigns"]})

    def test_filter_context_includes_inactive_campaigns_with_history_permission(self):
        inactive = _make_campaign("Inactiva2")
        inactive.is_active = False
        inactive.save(update_fields=["is_active"])
        self.staff.user_permissions.add(Permission.objects.get(codename="view_historical_campaigns"))
        request = self.factory.get("/")
        request.user = self.staff
        request.active_campaign = None
        context = get_filter_context(request)
        self.assertIn(inactive.pk, {campaign.pk for campaign in context["filter_campaigns"]})
