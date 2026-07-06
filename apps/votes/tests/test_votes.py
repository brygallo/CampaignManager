import json

from django.http import QueryDict
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.authentication.tests.factories import UserFactory
from apps.locations.tests.factories import CantonFactory, ParishFactory, ProvinceFactory
from apps.votes.forms import ElectoralDistrictForm, ElectoralWatcherForm, resolve_electoral_district
from apps.votes.models import (
    ElectoralCandidateOption,
    ElectoralDignity,
    ElectoralDistrict,
    ElectoralResultLine,
    ElectoralResultReport,
    ElectoralTable,
    ElectoralTableAssignment,
    ElectoralVenue,
)
from apps.votes.services import ElectoralReportDashboardService
from apps.votes.views import ElectoralReportDetailView


class ElectoralWatcherFormTests(TestCase):
    def test_dignities_are_limited_to_selected_parish_districts(self):
        province = ProvinceFactory()
        canton = CantonFactory(province=province)
        parish = ParishFactory(canton=canton)
        other_parish = ParishFactory()
        included = ElectoralDignity.objects.create(
            name="Alcaldia",
            scope=ElectoralDignity.Scope.CANTON,
        )
        excluded = ElectoralDignity.objects.create(
            name="Junta parroquial",
            scope=ElectoralDignity.Scope.PARISH,
        )
        ElectoralDistrict.objects.create(
            dignity=included,
            name="Canton",
            kind=ElectoralDistrict.DistrictKind.CANTON,
            canton=canton,
        )
        excluded_district = ElectoralDistrict.objects.create(
            dignity=excluded,
            name="Otra parroquia",
            kind=ElectoralDistrict.DistrictKind.PARISH,
        )
        excluded_district.parishes.add(other_parish)
        ElectoralCandidateOption.objects.create(
            district=included.districts.get(),
            list_code="1",
            candidate_name="Candidata",
        )

        form = ElectoralWatcherForm(data={"parish": parish.pk})

        self.assertEqual(list(form.fields["dignity"].queryset), [included])

    def test_resolves_province_canton_and_grouped_parish_districts(self):
        province = ProvinceFactory(name="Morona Santiago")
        canton = CantonFactory(province=province, name="Morona")
        rural_parish = ParishFactory(canton=canton, name="Cuchaentza", kind="RURAL")
        grouped_parish = ParishFactory(canton=canton, name="Sevilla Don Bosco", kind="RURAL")

        prefect = ElectoralDignity.objects.create(
            name="Prefecto",
            scope=ElectoralDignity.Scope.PROVINCE,
        )
        mayor = ElectoralDignity.objects.create(
            name="Alcalde",
            scope=ElectoralDignity.Scope.CANTON,
        )
        rural_council = ElectoralDignity.objects.create(
            name="Concejales rurales",
            scope=ElectoralDignity.Scope.DISTRICT,
            parish_kind_rule=ElectoralDignity.ParishKindRule.RURAL,
        )
        province_district = ElectoralDistrict.objects.create(
            dignity=prefect,
            name="Morona Santiago",
            kind=ElectoralDistrict.DistrictKind.PROVINCE,
            province=province,
        )
        canton_district = ElectoralDistrict.objects.create(
            dignity=mayor,
            name="Morona",
            kind=ElectoralDistrict.DistrictKind.CANTON,
            canton=canton,
        )
        rural_district = ElectoralDistrict.objects.create(
            dignity=rural_council,
            name="Rurales Morona",
            kind=ElectoralDistrict.DistrictKind.RURAL,
        )
        rural_district.parishes.add(rural_parish, grouped_parish)

        self.assertEqual(
            resolve_electoral_district(parish_id=rural_parish.pk, dignity_id=prefect.pk),
            province_district,
        )
        self.assertEqual(
            resolve_electoral_district(parish_id=rural_parish.pk, dignity_id=mayor.pk),
            canton_district,
        )
        self.assertEqual(
            resolve_electoral_district(parish_id=rural_parish.pk, dignity_id=rural_council.pk),
            rural_district,
        )

    def test_dignity_respects_urban_and_rural_parish_rules(self):
        province = ProvinceFactory()
        canton = CantonFactory(province=province)
        urban_parish = ParishFactory(canton=canton, kind="URBANA")
        rural_parish = ParishFactory(canton=canton, kind="RURAL")
        urban_dignity = ElectoralDignity.objects.create(
            name="Concejales urbanos",
            scope=ElectoralDignity.Scope.DISTRICT,
            parish_kind_rule=ElectoralDignity.ParishKindRule.URBAN,
        )
        rural_dignity = ElectoralDignity.objects.create(
            name="Junta parroquial",
            scope=ElectoralDignity.Scope.PARISH,
            parish_kind_rule=ElectoralDignity.ParishKindRule.RURAL,
        )
        urban_district = ElectoralDistrict.objects.create(
            dignity=urban_dignity,
            name="Urbanas",
            kind=ElectoralDistrict.DistrictKind.URBAN,
        )
        urban_district.parishes.add(urban_parish)
        rural_district = ElectoralDistrict.objects.create(
            dignity=rural_dignity,
            name="Rural",
            kind=ElectoralDistrict.DistrictKind.PARISH,
        )
        rural_district.parishes.add(rural_parish)

        urban_form = ElectoralWatcherForm(data={"parish": urban_parish.pk})
        rural_form = ElectoralWatcherForm(data={"parish": rural_parish.pk})

        self.assertEqual(list(urban_form.fields["dignity"].queryset), [urban_dignity])
        self.assertEqual(list(rural_form.fields["dignity"].queryset), [rural_dignity])

    def test_watcher_cannot_submit_unassigned_table(self):
        watcher = UserFactory()
        other_watcher = UserFactory()
        parish = ParishFactory()
        venue = ElectoralVenue.objects.create(parish=parish, name="Recinto")
        table = ElectoralTable.objects.create(venue=venue, number="1")
        ElectoralTableAssignment.objects.create(table=table, watcher=other_watcher)
        dignity = ElectoralDignity.objects.create(
            name="Alcalde",
            scope=ElectoralDignity.Scope.CANTON,
        )
        district = ElectoralDistrict.objects.create(
            dignity=dignity,
            name="Cantonal",
            kind=ElectoralDistrict.DistrictKind.CANTON,
            canton=parish.canton,
        )
        ElectoralCandidateOption.objects.create(
            district=district,
            list_code="A",
            candidate_name="Candidato",
        )

        form = ElectoralWatcherForm(
            data={
                "parish": parish.pk,
                "venue": venue.pk,
                "table": table.pk,
                "dignity": dignity.pk,
                "blank_votes": 0,
                "null_votes": 0,
                f"candidate_{district.candidate_options.get().pk}": 10,
            },
            watcher=watcher,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("table", form.errors)


class ElectoralDistrictFormTests(TestCase):
    def test_parish_scope_requires_one_parish_only(self):
        parish = ParishFactory(kind="RURAL")
        other_parish = ParishFactory(kind="RURAL")
        dignity = ElectoralDignity.objects.create(
            name="Junta parroquial",
            scope=ElectoralDignity.Scope.PARISH,
            parish_kind_rule=ElectoralDignity.ParishKindRule.RURAL,
        )

        form = ElectoralDistrictForm(
            data={
                "dignity": dignity.pk,
                "name": "Junta agrupada",
                "kind": ElectoralDistrict.DistrictKind.PARISH,
                "parishes": [parish.pk, other_parish.pk],
                "seats": 5,
                "order": 1,
                "is_active": True,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("parishes", form.errors)

    def test_district_scope_allows_grouped_parishes_for_councilors(self):
        parish = ParishFactory(kind="RURAL")
        other_parish = ParishFactory(kind="RURAL")
        dignity = ElectoralDignity.objects.create(
            name="Concejales rurales",
            scope=ElectoralDignity.Scope.DISTRICT,
            parish_kind_rule=ElectoralDignity.ParishKindRule.RURAL,
        )

        form = ElectoralDistrictForm(
            data={
                "dignity": dignity.pk,
                "name": "Rurales agrupadas",
                "kind": ElectoralDistrict.DistrictKind.RURAL,
                "parishes": [parish.pk, other_parish.pk],
                "seats": 3,
                "order": 1,
                "is_active": True,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)


class ElectoralReportPayloadTests(TestCase):
    def test_builds_fixed_dignity_tabs_from_configured_dignities(self):
        prefect = ElectoralDignity.objects.create(
            name="Prefecto/a",
            scope=ElectoralDignity.Scope.PROVINCE,
            parish_kind_rule=ElectoralDignity.ParishKindRule.ALL,
            order=10,
        )
        mayor = ElectoralDignity.objects.create(
            name="Alcalde/sa de Morona",
            scope=ElectoralDignity.Scope.CANTON,
            parish_kind_rule=ElectoralDignity.ParishKindRule.ALL,
            order=20,
        )
        ElectoralDignity.objects.create(
            name="Concejales urbanos de Morona",
            scope=ElectoralDignity.Scope.DISTRICT,
            parish_kind_rule=ElectoralDignity.ParishKindRule.URBAN,
            order=30,
        )
        ElectoralDignity.objects.create(
            name="Concejales rurales de Morona",
            scope=ElectoralDignity.Scope.DISTRICT,
            parish_kind_rule=ElectoralDignity.ParishKindRule.RURAL,
            order=40,
        )
        ElectoralDignity.objects.create(
            name="Vocales de junta parroquial",
            scope=ElectoralDignity.Scope.PARISH,
            parish_kind_rule=ElectoralDignity.ParishKindRule.RURAL,
            order=50,
        )

        query = QueryDict("", mutable=True)
        query["dignity"] = str(mayor.pk)
        query["parish"] = "7"
        query["page"] = "3"
        tabs = ElectoralReportDashboardService({"dignity": mayor}).build_dignity_tabs(query)

        self.assertEqual(
            [tab["label"] for tab in tabs],
            [
                "Prefectura",
                "Alcaldía",
                "Concejales urbanos",
                "Concejales rurales",
                "Juntas parroquiales",
            ],
        )
        self.assertEqual(tabs[0]["dignity_id"], prefect.pk)
        self.assertTrue(tabs[1]["is_active"])
        self.assertIn(f"dignity={prefect.pk}", tabs[0]["query_string"])
        self.assertIn("parish=7", tabs[0]["query_string"])
        self.assertNotIn("page=3", tabs[0]["query_string"])

    def test_operational_summary_counts_expected_received_and_vote_types(self):
        parish = ParishFactory()
        venue = ElectoralVenue.objects.create(parish=parish, name="Recinto")
        table_one = ElectoralTable.objects.create(venue=venue, number="1")
        ElectoralTable.objects.create(venue=venue, number="2")
        dignity = ElectoralDignity.objects.create(
            name="Alcalde",
            scope=ElectoralDignity.Scope.CANTON,
        )
        district = ElectoralDistrict.objects.create(
            dignity=dignity,
            name="Cantonal",
            kind=ElectoralDistrict.DistrictKind.CANTON,
            canton=parish.canton,
        )
        option = ElectoralCandidateOption.objects.create(
            district=district,
            list_code="A",
            candidate_name="Candidato",
        )
        report = ElectoralResultReport.objects.create(
            parish=parish,
            venue=venue,
            table=table_one,
            dignity=dignity,
            district=district,
        )
        ElectoralResultLine.objects.create(
            report=report,
            line_type=ElectoralResultLine.LineType.CANDIDATE,
            candidate_option=option,
            list_code=option.list_code,
            candidate_name=option.candidate_name,
            votes=30,
            order=1,
        )
        ElectoralResultLine.objects.create(
            report=report,
            line_type=ElectoralResultLine.LineType.BLANK,
            list_code="BLANCOS",
            votes=2,
            order=2,
        )
        ElectoralResultLine.objects.create(
            report=report,
            line_type=ElectoralResultLine.LineType.NULL,
            list_code="NULOS",
            votes=3,
            order=3,
        )

        payload = ElectoralReportDashboardService({"dignity": dignity}).build_payload()
        summary = payload["operational_summary"]

        self.assertEqual(summary["expected_reports"], 2)
        self.assertEqual(summary["received_reports"], 1)
        self.assertEqual(summary["progress_percent"], 50.0)
        self.assertEqual(summary["valid_votes"], 30)
        self.assertEqual(summary["blank_votes"], 2)
        self.assertEqual(summary["null_votes"], 3)
        self.assertIsNotNone(summary["latest_update"])

    def test_candidate_ranking_lead_margin_and_parish_summary(self):
        parish = ParishFactory(name="Macas")
        venue = ElectoralVenue.objects.create(parish=parish, name="Recinto")
        table = ElectoralTable.objects.create(venue=venue, number="1")
        dignity = ElectoralDignity.objects.create(
            name="Alcalde",
            scope=ElectoralDignity.Scope.CANTON,
        )
        district = ElectoralDistrict.objects.create(
            dignity=dignity,
            name="Cantonal",
            kind=ElectoralDistrict.DistrictKind.CANTON,
            canton=parish.canton,
        )
        first = ElectoralCandidateOption.objects.create(
            district=district,
            list_code="A",
            candidate_name="Primera",
        )
        second = ElectoralCandidateOption.objects.create(
            district=district,
            list_code="B",
            candidate_name="Segundo",
        )
        report = ElectoralResultReport.objects.create(
            parish=parish,
            venue=venue,
            table=table,
            dignity=dignity,
            district=district,
        )
        ElectoralResultLine.objects.create(
            report=report,
            line_type=ElectoralResultLine.LineType.CANDIDATE,
            candidate_option=first,
            list_code=first.list_code,
            candidate_name=first.candidate_name,
            votes=127,
            order=1,
        )
        ElectoralResultLine.objects.create(
            report=report,
            line_type=ElectoralResultLine.LineType.CANDIDATE,
            candidate_option=second,
            list_code=second.list_code,
            candidate_name=second.candidate_name,
            votes=100,
            order=2,
        )

        payload = ElectoralReportDashboardService({"dignity": dignity}).build_payload()

        self.assertEqual(payload["candidate_ranking"][0]["label"], "A - Primera")
        self.assertEqual(payload["candidate_ranking"][0]["trend_state"], "Lidera")
        self.assertEqual(payload["lead_margin"]["votes"], 27)
        self.assertEqual(payload["lead_margin"]["percent"], 11.8)
        self.assertEqual(payload["parish_summary"][0]["parish"], "Macas")
        self.assertEqual(payload["parish_summary"][0]["rows"][0]["votes"], 127)

    def test_progress_status_groups_by_venue_table_and_dignity(self):
        parish = ParishFactory()
        partial_venue = ElectoralVenue.objects.create(parish=parish, name="Recinto parcial")
        submitted_table = ElectoralTable.objects.create(venue=partial_venue, number="1")
        missing_table = ElectoralTable.objects.create(venue=partial_venue, number="2")
        observed_venue = ElectoralVenue.objects.create(parish=parish, name="Recinto observado")
        observed_table = ElectoralTable.objects.create(venue=observed_venue, number="3")
        validated_venue = ElectoralVenue.objects.create(parish=parish, name="Recinto validado")
        validated_table = ElectoralTable.objects.create(venue=validated_venue, number="4")
        dignity = ElectoralDignity.objects.create(
            name="Alcalde",
            scope=ElectoralDignity.Scope.CANTON,
        )
        district = ElectoralDistrict.objects.create(
            dignity=dignity,
            name="Cantonal",
            kind=ElectoralDistrict.DistrictKind.CANTON,
            canton=parish.canton,
        )
        for table, status in (
            (submitted_table, ElectoralResultReport.Status.SUBMITTED),
            (observed_table, ElectoralResultReport.Status.OBSERVED),
            (validated_table, ElectoralResultReport.Status.VALIDATED),
        ):
            ElectoralResultReport.objects.create(
                parish=parish,
                venue=table.venue,
                table=table,
                dignity=dignity,
                district=district,
                status=status,
            )

        payload = ElectoralReportDashboardService({"dignity": dignity}).build_payload()
        table_statuses = {
            row["label"]: (row["status_label"], row["status_badge_class"])
            for row in payload["progress_status"]["tables"]
        }
        venue_statuses = {
            row["label"]: row["status_label"] for row in payload["progress_status"]["venues"]
        }
        dignity_statuses = {
            row["label"]: row["status_label"] for row in payload["progress_status"]["dignities"]
        }

        self.assertEqual(table_statuses["1 - Mixta"], ("Ingresada", "badge-light-primary"))
        self.assertEqual(table_statuses["2 - Mixta"], ("Sin acta", "badge-light-secondary"))
        self.assertEqual(table_statuses["3 - Mixta"], ("Observada", "badge-light-danger"))
        self.assertEqual(table_statuses["4 - Mixta"], ("Validada", "badge-light-success"))
        self.assertEqual(venue_statuses["Recinto parcial"], "Parcial")
        self.assertEqual(dignity_statuses["Alcalde"], "Parcial")

    def test_report_detail_drawer_returns_read_only_acta_payload(self):
        user = UserFactory()
        parish = ParishFactory(name="Macas")
        venue = ElectoralVenue.objects.create(parish=parish, name="Recinto central")
        table = ElectoralTable.objects.create(venue=venue, number="1")
        dignity = ElectoralDignity.objects.create(
            name="Alcalde",
            scope=ElectoralDignity.Scope.CANTON,
        )
        district = ElectoralDistrict.objects.create(
            dignity=dignity,
            name="Cantonal",
            kind=ElectoralDistrict.DistrictKind.CANTON,
            canton=parish.canton,
        )
        option = ElectoralCandidateOption.objects.create(
            district=district,
            list_code="A",
            candidate_name="Candidata",
        )
        report = ElectoralResultReport.objects.create(
            parish=parish,
            venue=venue,
            table=table,
            dignity=dignity,
            district=district,
            watcher=user,
            voters_count=11,
        )
        ElectoralResultLine.objects.create(
            report=report,
            line_type=ElectoralResultLine.LineType.CANDIDATE,
            candidate_option=option,
            list_code=option.list_code,
            candidate_name=option.candidate_name,
            votes=10,
            order=1,
        )
        ElectoralResultLine.objects.create(
            report=report,
            line_type=ElectoralResultLine.LineType.BLANK,
            list_code="BLANCOS",
            votes=1,
            order=2,
        )

        request = RequestFactory().get(
            reverse("votes:report_detail", args=[report.pk]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        request.user = user
        response = ElectoralReportDetailView.as_view()(request, pk=report.pk)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertTrue(payload["read_only"])
        self.assertIn("Acta mesa 1", payload["title"])
        self.assertIn("Recinto central", payload["template"])
        self.assertIn("Candidata", payload["template"])
