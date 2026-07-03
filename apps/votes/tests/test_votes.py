from django.test import TestCase

from apps.authentication.tests.factories import UserFactory
from apps.locations.tests.factories import CantonFactory, ParishFactory, ProvinceFactory
from apps.votes.forms import ElectoralDistrictForm, ElectoralWatcherForm, resolve_electoral_district
from apps.votes.models import (
    ElectoralCandidateOption,
    ElectoralDignity,
    ElectoralDistrict,
    ElectoralResultReport,
    ElectoralTable,
    ElectoralTableAssignment,
    ElectoralVenue,
)


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
