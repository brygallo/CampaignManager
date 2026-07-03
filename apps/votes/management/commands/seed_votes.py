"""Siembra datos de demostración para resultados electorales.

Uso:
    python manage.py tenant_command seed_votes --schema=<tenant>
    python manage.py tenant_command seed_votes --schema=<tenant> --reset
"""
from __future__ import annotations

import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.locations.models import Canton, Parish, Province
from apps.votes.forms import electoral_districts_for_parish
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
from tracing.middleware import TracingMiddleware


User = get_user_model()


PARISHES = [
    ("MACAS", "VOTEMACAS", Parish.ParishKind.URBANA),
    ("SEVILLA DON BOSCO", "VOTESEVDB", Parish.ParishKind.RURAL),
    ("SAN ISIDRO", "VOTESISID", Parish.ParishKind.RURAL),
    ("GENERAL PROAÑO", "VOTEGPROA", Parish.ParishKind.RURAL),
    ("RÍO BLANCO", "VOTERIOBL", Parish.ParishKind.RURAL),
]

VENUES = {
    "MACAS": [
        ("Unidad Educativa Macas", "-2.308240", "-78.111420", 4),
        ("Escuela Eloy Alfaro", "-2.301120", "-78.119870", 3),
        ("Colegio 29 de Mayo", "-2.315460", "-78.104210", 3),
    ],
    "SEVILLA DON BOSCO": [
        ("Escuela Sevilla Don Bosco", "-2.257990", "-78.158320", 3),
        ("Casa Comunal Don Bosco", "-2.276510", "-78.169180", 2),
    ],
    "SAN ISIDRO": [
        ("Unidad Educativa San Isidro", "-2.236880", "-78.180210", 3),
    ],
    "GENERAL PROAÑO": [
        ("Escuela General Proaño", "-2.276240", "-78.088650", 2),
    ],
    "RÍO BLANCO": [
        ("Escuela Río Blanco", "-2.349420", "-78.165550", 2),
    ],
}

CANDIDATE_POOLS = {
    "Prefecto/a": [
        ("18", "Tiyua Uyunkar Kaniras - Pachakutik"),
        ("5", "María Tsamaraint Wajai - Revolución Ciudadana"),
        ("6-75", "Carlos Alberto Rivadeneira - PSC / Madera de Guerrero"),
        ("21-25", "Karina Zhunio Vargas - CREO / Construye"),
    ],
    "Alcalde/sa de Morona": [
        ("35", "Francisco Andramuño - MOVER"),
        ("5", "Rocío Tankamash Jimpikit - Revolución Ciudadana"),
        ("6-75", "Luis Fernando Calle Ortiz - PSC / Madera de Guerrero"),
        ("1-2-33", "Patricio Antún Chiriap - Centro Democrático / UP / RETO"),
    ],
    "Concejales urbanos de Morona": [
        ("5", "Verónica Wisuma Tiwi - Revolución Ciudadana"),
        ("6-75", "Andrés Sebastián Cobo - PSC / Madera de Guerrero"),
        ("21-25", "Hernán Patricio Tello - CREO / Construye"),
    ],
    "Concejales rurales de Morona": [
        ("18", "Mariana Sharup Pinchupá - Pachakutik"),
        ("5-72", "Edwin Oswaldo Patiño - RC / Sí Podemos"),
        ("21-25", "Esthela Naichap Pujupat - CREO / Construye"),
    ],
    "Vocales de junta parroquial": [
        ("18", "Pachakutik - Equipo comunitario"),
        ("5", "Revolución Ciudadana - Unidad parroquial"),
        ("6-23", "PSC / SUMA - Acuerdo parroquial"),
    ],
}

WATCHERS = [
    ("veedor.macas", "veedor.macas@example.ec", "Ana Lucía Shakai", "Tanchim"),
    ("veedor.rural1", "veedor.rural1@example.ec", "Miguel Ángel", "Naichap"),
    ("veedor.rural2", "veedor.rural2@example.ec", "Sandra Beatriz", "Chiriap"),
]


class Command(BaseCommand):
    help = "Siembra dignidades, circunscripciones, recintos, mesas, veedores y actas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Borra los datos de votaciones antes de sembrar.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        random.seed(20260703)
        self._stamp_audit_user()

        if opts["reset"]:
            self._reset()

        province = self._province()
        canton = self._canton(province)
        parishes = self._parishes(canton)
        dignities = self._dignities()
        districts = self._districts(province, canton, parishes, dignities)
        candidates = self._candidates(districts)
        venues, tables = self._venues_and_tables(parishes)
        watchers = self._watchers()
        assignments = self._assignments(tables, watchers)
        reports = self._reports(tables, watchers, candidates)

        self.stdout.write(self.style.SUCCESS(f"Dignidades: {len(dignities)}"))
        self.stdout.write(self.style.SUCCESS(f"Circunscripciones: {len(districts)}"))
        self.stdout.write(self.style.SUCCESS(f"Candidaturas: {len(candidates)}"))
        self.stdout.write(self.style.SUCCESS(f"Recintos: {len(venues)}"))
        self.stdout.write(self.style.SUCCESS(f"Mesas: {len(tables)}"))
        self.stdout.write(self.style.SUCCESS(f"Asignaciones: {assignments}"))
        self.stdout.write(self.style.SUCCESS(f"Actas: {reports}"))
        self.stdout.write(self.style.SUCCESS("✔ Votaciones sembradas."))

    def _stamp_audit_user(self):
        user = User.objects.filter(is_superuser=True).order_by("id").first()
        if user is not None:
            TracingMiddleware.thread_local.user = user

    def _reset(self):
        ElectoralResultLine.objects.all().delete()
        ElectoralResultReport.objects.all().delete()
        ElectoralTableAssignment.objects.all().delete()
        ElectoralTable.objects.all().delete()
        ElectoralVenue.objects.all().delete()
        ElectoralCandidateOption.objects.all().delete()
        ElectoralDistrict.objects.all().delete()
        ElectoralDignity.objects.all().delete()
        self.stdout.write(self.style.WARNING("Datos previos de votaciones borrados."))

    def _province(self):
        province, _ = Province.objects.update_or_create(
            code="14",
            defaults={"name": "Morona Santiago"},
        )
        return province

    def _canton(self, province):
        canton, _ = Canton.objects.update_or_create(
            code="1401",
            defaults={"province": province, "name": "Morona"},
        )
        return canton

    def _parishes(self, canton):
        parishes = {}
        for name, code, kind in PARISHES:
            parish, _ = Parish.objects.get_or_create(
                canton=canton,
                name=name,
                defaults={"code": code, "kind": kind},
            )
            if parish.kind != kind:
                parish.kind = kind
                parish.save(update_fields=["kind"])
            parishes[name] = parish
        return parishes

    def _dignities(self):
        specs = [
            ("Prefecto/a", ElectoralDignity.Scope.PROVINCE, ElectoralDignity.ParishKindRule.ALL, 1, 10),
            ("Alcalde/sa de Morona", ElectoralDignity.Scope.CANTON, ElectoralDignity.ParishKindRule.ALL, 1, 20),
            ("Concejales urbanos de Morona", ElectoralDignity.Scope.DISTRICT, ElectoralDignity.ParishKindRule.URBAN, 5, 30),
            ("Concejales rurales de Morona", ElectoralDignity.Scope.DISTRICT, ElectoralDignity.ParishKindRule.RURAL, 5, 40),
            ("Vocales de junta parroquial", ElectoralDignity.Scope.PARISH, ElectoralDignity.ParishKindRule.RURAL, 5, 50),
        ]
        dignities = {}
        for name, scope, rule, seats, order in specs:
            dignity, _ = ElectoralDignity.objects.update_or_create(
                name=name,
                defaults={
                    "scope": scope,
                    "parish_kind_rule": rule,
                    "seats": seats,
                    "order": order,
                    "is_active": True,
                },
            )
            dignities[name] = dignity
        return dignities

    def _districts(self, province, canton, parishes, dignities):
        districts = {}
        prefect, _ = ElectoralDistrict.objects.update_or_create(
            dignity=dignities["Prefecto/a"],
            name="Morona Santiago",
            defaults={
                "kind": ElectoralDistrict.DistrictKind.PROVINCE,
                "province": province,
                "canton": None,
                "seats": 1,
                "order": 10,
                "is_active": True,
            },
        )
        districts[prefect.name] = prefect

        mayor, _ = ElectoralDistrict.objects.update_or_create(
            dignity=dignities["Alcalde/sa de Morona"],
            name="Cantón Morona",
            defaults={
                "kind": ElectoralDistrict.DistrictKind.CANTON,
                "province": None,
                "canton": canton,
                "seats": 1,
                "order": 20,
                "is_active": True,
            },
        )
        districts[mayor.name] = mayor

        urban, _ = ElectoralDistrict.objects.update_or_create(
            dignity=dignities["Concejales urbanos de Morona"],
            name="Circunscripción urbana Morona",
            defaults={
                "kind": ElectoralDistrict.DistrictKind.URBAN,
                "seats": 5,
                "order": 30,
                "is_active": True,
            },
        )
        urban.parishes.set([parishes["MACAS"]])
        districts[urban.name] = urban

        rural_parishes = [parish for name, parish in parishes.items() if name != "MACAS"]
        rural, _ = ElectoralDistrict.objects.update_or_create(
            dignity=dignities["Concejales rurales de Morona"],
            name="Circunscripción rural Morona",
            defaults={
                "kind": ElectoralDistrict.DistrictKind.RURAL,
                "seats": 5,
                "order": 40,
                "is_active": True,
            },
        )
        rural.parishes.set(rural_parishes)
        districts[rural.name] = rural

        for order, parish in enumerate(rural_parishes, start=51):
            district, _ = ElectoralDistrict.objects.update_or_create(
                dignity=dignities["Vocales de junta parroquial"],
                name=f"Junta parroquial {parish.name.title()}",
                defaults={
                    "kind": ElectoralDistrict.DistrictKind.PARISH,
                    "seats": 5,
                    "order": order,
                    "is_active": True,
                },
            )
            district.parishes.set([parish])
            districts[district.name] = district
        return districts

    def _candidates(self, districts):
        candidates = []
        for district in districts.values():
            pool = CANDIDATE_POOLS[district.dignity.name]
            for order, (list_code, candidate_name) in enumerate(pool, start=1):
                candidate, _ = ElectoralCandidateOption.objects.update_or_create(
                    district=district,
                    list_code=list_code,
                    candidate_name=candidate_name,
                    defaults={"order": order, "is_active": True},
                )
                candidates.append(candidate)
        return candidates

    def _venues_and_tables(self, parishes):
        venues = []
        tables = []
        for parish_name, venue_specs in VENUES.items():
            parish = parishes[parish_name]
            for venue_name, lat, lng, table_count in venue_specs:
                venue, _ = ElectoralVenue.objects.update_or_create(
                    parish=parish,
                    name=venue_name,
                    defaults={
                        "latitude": Decimal(lat),
                        "longitude": Decimal(lng),
                        "is_active": True,
                    },
                )
                venues.append(venue)
                for number in range(1, table_count + 1):
                    gender = ElectoralTable.Gender.FEMALE if number % 2 else ElectoralTable.Gender.MALE
                    table, _ = ElectoralTable.objects.update_or_create(
                        venue=venue,
                        number=str(number),
                        gender=gender,
                        defaults={
                            "registered_voters": random.randint(380, 460),
                            "is_active": True,
                        },
                    )
                    tables.append(table)
        return venues, tables

    def _watchers(self):
        watchers = []
        for username, email, first_name, last_name in WATCHERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "is_active": True,
                },
            )
            if created:
                user.set_password("Veedores2026!")
                user.save()
            watchers.append(user)
        return watchers

    def _assignments(self, tables, watchers):
        count = 0
        for index, table in enumerate(tables):
            watcher = watchers[index % len(watchers)]
            _, created = ElectoralTableAssignment.objects.get_or_create(
                table=table,
                watcher=watcher,
                defaults={"notes": "Asignación generada por seed_votes.", "is_active": True},
            )
            if created:
                count += 1
        return count

    def _reports(self, tables, watchers, candidates):
        candidates_by_district = {}
        for candidate in candidates:
            candidates_by_district.setdefault(candidate.district_id, []).append(candidate)

        count = 0
        statuses = [
            ElectoralResultReport.Status.SUBMITTED,
            ElectoralResultReport.Status.VALIDATED,
            ElectoralResultReport.Status.SUBMITTED,
            ElectoralResultReport.Status.OBSERVED,
        ]
        for table_index, table in enumerate(tables):
            parish = table.venue.parish
            for district in electoral_districts_for_parish(parish):
                report, _ = ElectoralResultReport.objects.update_or_create(
                    table=table,
                    dignity=district.dignity,
                    district=district,
                    defaults={
                        "parish": parish,
                        "venue": table.venue,
                        "watcher": watchers[table_index % len(watchers)],
                        "status": statuses[(table_index + district.order) % len(statuses)],
                        "validation_notes": "",
                        "is_active": True,
                    },
                )
                line_count = self._report_lines(report, candidates_by_district[district.pk])
                report.voters_count = line_count
                report.save(update_fields=["voters_count"])
                count += 1
        return count

    def _report_lines(self, report, candidates):
        report.lines.all().delete()
        voters_count = random.randint(180, 360)
        blank_votes = random.randint(2, 12)
        null_votes = random.randint(4, 18)
        candidate_total = voters_count - blank_votes - null_votes
        weights = [random.randint(18, 45) for _ in candidates]
        weight_total = sum(weights)
        votes = [(candidate_total * weight) // weight_total for weight in weights]
        votes[0] += candidate_total - sum(votes)

        for order, (candidate, vote_count) in enumerate(zip(candidates, votes), start=1):
            ElectoralResultLine.objects.create(
                report=report,
                line_type=ElectoralResultLine.LineType.CANDIDATE,
                candidate_option=candidate,
                list_code=candidate.list_code,
                candidate_name=candidate.candidate_name,
                votes=vote_count,
                order=order,
            )
        ElectoralResultLine.objects.create(
            report=report,
            line_type=ElectoralResultLine.LineType.BLANK,
            list_code="BLANCOS",
            votes=blank_votes,
            order=len(candidates) + 1,
        )
        ElectoralResultLine.objects.create(
            report=report,
            line_type=ElectoralResultLine.LineType.NULL,
            list_code="NULOS",
            votes=null_votes,
            order=len(candidates) + 2,
        )
        return voters_count
