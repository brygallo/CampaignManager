"""Siembra solicitudes de agenda política y eventos en distintos estados.

Genera ~12 solicitudes (PENDING / IN_REVIEW / APPROVED / REJECTED) y ~8
eventos (DRAFT / SCHEDULED / DONE) ligados a la campaña activa, con
coordenadas tentativas jitterizadas alrededor de Macas.

Uso:
    python manage.py tenant_command seed_political_agenda --schema=<tenant>

Requiere previamente:
    seed_campaigns, seed_political_agenda_catalog
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.campaigns.models import Campaign
from apps.political_agenda.models import (
    AgendaEventType,
    PoliticalAgendaEvent,
    PoliticalAgendaRequest,
)


User = get_user_model()


REQUESTS = [
    # (title, type_code, priority, requester, org, state)
    (
        "Reunión con dirigentes barriales La Loma",
        "REUNION",
        "MEDIA",
        "Carlos Tankamash",
        "Comité barrial La Loma",
        "APPROVED",
    ),
    (
        "Visita a feria de productores Macas",
        "VISITA",
        "ALTA",
        "Asociación Agroproductora",
        "Asociación de Productores Morona",
        "APPROVED",
    ),
    (
        "Recorrido casa por casa Yantzaza",
        "RECORRIDO",
        "MEDIA",
        "Equipo de campaña",
        "Movimiento territorial",
        "PENDING",
    ),
    (
        "Mitin en parque central Sevilla Don Bosco",
        "MITIN",
        "ALTA",
        "Federación Shuar",
        "FICSH local",
        "IN_REVIEW",
    ),
    (
        "Entrevista Radio La Voz del Upano",
        "ENTREVISTA",
        "ALTA",
        "Mario Naichap",
        "Radio La Voz del Upano",
        "APPROVED",
    ),
    (
        "Rueda de prensa propuesta vial",
        "RUEDA_PRENSA",
        "URGENTE",
        "Coordinadora de prensa",
        "Equipo de campaña",
        "APPROVED",
    ),
    (
        "Reunión con docentes UEP Don Bosco",
        "REUNION",
        "MEDIA",
        "Mariana Sharup",
        "UEP Don Bosco",
        "PENDING",
    ),
    ("Visita comunidad Tunants", "VISITA", "MEDIA", "Síndico Wisuma", "Centro Tunants", "PENDING"),
    (
        "Mitin cierre semana 1",
        "MITIN",
        "ALTA",
        "Equipo de campaña",
        "Movimiento territorial",
        "REJECTED",
    ),
    (
        "Recorrido feria del 9 de Octubre",
        "RECORRIDO",
        "BAJA",
        "Comité 9 de Octubre",
        "Comité barrial",
        "PENDING",
    ),
    (
        "Reunión con transportistas urbanos",
        "REUNION",
        "ALTA",
        "Cooperativa San Cristóbal",
        "Coop. de transportes",
        "IN_REVIEW",
    ),
    (
        "Visita Centro de Salud General Proaño",
        "VISITA",
        "MEDIA",
        "Dra. Rocío Vargas",
        "MSP - Subcentro",
        "APPROVED",
    ),
]


# Macas, Morona Santiago — punto base para jitter de coordenadas tentativas.
BASE_LAT = Decimal("-2.310000")
BASE_LNG = Decimal("-78.120000")


def _at(days_from_now: int, hour: int = 9, minute: int = 0):
    base = timezone.localtime() + timedelta(days=days_from_now)
    return base.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _jitter_coords(rng: random.Random):
    """Pequeña dispersión (~0.04°, ~4 km) alrededor del punto base."""
    return (
        BASE_LAT + Decimal(str(round(rng.uniform(-0.04, 0.04), 6))),
        BASE_LNG + Decimal(str(round(rng.uniform(-0.04, 0.04), 6))),
    )


class Command(BaseCommand):
    help = "Siembra solicitudes y eventos de agenda política."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true", help="Borra eventos y solicitudes antes de sembrar."
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts.get("reset"):
            PoliticalAgendaEvent.objects.all().delete()
            PoliticalAgendaRequest.objects.all().delete()
            self.stdout.write(self.style.WARNING("Datos previos borrados."))

        if not AgendaEventType.objects.exists():
            self.stdout.write(self.style.WARNING(
                "Catálogos vacíos. Corriendo seed_political_agenda_catalog…"
            ))
            call_command("seed_political_agenda_catalog")

        types_by_code = {t.code: t for t in AgendaEventType.objects.all()}

        campaign = (
            Campaign.objects.filter(name="Macas para Todos").first()
            or Campaign.objects.filter(state__gt=0).order_by("-start_date").first()
        )
        if campaign is None:
            self.stderr.write(self.style.ERROR("No hay campaña. Corre primero seed_campaigns."))
            return

        user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if user is None:
            self.stderr.write(self.style.ERROR("No hay usuarios."))
            return

        rng = random.Random(42)

        # solicitudes
        wf_req = PoliticalAgendaRequest.workflow
        approved_requests = []
        for i, (title, etype_code, priority, requester, org, state) in enumerate(REQUESTS):
            lat, lng = _jitter_coords(rng)

            req, created = PoliticalAgendaRequest.objects.get_or_create(
                campaign=campaign,
                title=title,
                defaults={
                    "event_type": types_by_code.get(etype_code, types_by_code["OTRO"]),
                    "priority": priority,
                    "requester_name": requester,
                    "requester_phone": f"09{60000000 + i * 11111}",
                    "organization": org,
                    "proposed_start_at": _at(7 + i, hour=9 + (i % 6), minute=0),
                    "proposed_end_at": _at(7 + i, hour=11 + (i % 6), minute=0),
                    "address": "Por confirmar",
                    "latitude": lat,
                    "longitude": lng,
                    "objective": "Coordinar agenda territorial.",
                    "expected_attendees": 20 + (i * 7) % 80,
                    "created_by": user,
                },
            )
            if req.state == wf_req.PENDING:
                if state == "IN_REVIEW":
                    req.send_to_review(user=user)
                    req.save()
                elif state == "APPROVED":
                    req.approve(user=user)
                    req.save()
                elif state == "REJECTED":
                    req.reject(
                        user=user, rejection_reason="Cruce de agenda con otro evento priorizado."
                    )
                    req.save()
            if req.state == wf_req.APPROVED:
                approved_requests.append(req)

        self.stdout.write(
            self.style.SUCCESS(f"Solicitudes: {PoliticalAgendaRequest.objects.count()}")
        )

        # eventos: SCHEDULED desde solicitudes aprobadas, DONE pasadas, DRAFT futuras
        wf_evt = PoliticalAgendaEvent.workflow
        events_made = 0
        for i, req in enumerate(approved_requests[:4]):
            evt, created = PoliticalAgendaEvent.objects.get_or_create(
                campaign=campaign,
                source_request=req,
                title=req.title,
                defaults={
                    "event_type": req.event_type,
                    "start_at": req.proposed_start_at or _at(10 + i, 9),
                    "end_at": req.proposed_end_at or _at(10 + i, 11),
                    "address": req.address or "Centro Macas",
                    "latitude": req.latitude,
                    "longitude": req.longitude,
                    "organizer_name": req.requester_name,
                    "organizer_phone": req.requester_phone,
                    "responsible": user,
                    "expected_attendees": req.expected_attendees,
                    "objective": req.objective,
                    "created_by": user,
                },
            )
            if evt.state == wf_evt.DRAFT:
                evt.schedule()
                evt.save()
            events_made += 1

        # eventos pasados marcados DONE
        for i in range(2):
            start = _at(-(7 + i * 3), hour=10)
            end = start + timedelta(hours=2)
            lat, lng = _jitter_coords(rng)
            evt, _c = PoliticalAgendaEvent.objects.get_or_create(
                campaign=campaign,
                title=f"Evento histórico Macas #{i + 1}",
                defaults={
                    "event_type": types_by_code["RECORRIDO"],
                    "start_at": start,
                    "end_at": end,
                    "address": "Centro de la parroquia",
                    "latitude": lat,
                    "longitude": lng,
                    "organizer_name": "Equipo de campaña",
                    "organizer_phone": "0999000000",
                    "responsible": user,
                    "expected_attendees": 80,
                    "objective": "Recorrido territorial.",
                    "result_notes": "Asistencia alta. Se recogieron compromisos de obra vial.",
                    "created_by": user,
                },
            )
            if evt.state == wf_evt.DRAFT:
                evt.schedule()
                evt.save()
            if evt.state == wf_evt.SCHEDULED:
                evt.mark_done()
                evt.save()
            events_made += 1

        # eventos en borrador
        for i in range(2):
            start = _at(20 + i * 4, hour=18)
            end = start + timedelta(hours=2)
            lat, lng = _jitter_coords(rng)
            evt, _c = PoliticalAgendaEvent.objects.get_or_create(
                campaign=campaign,
                title=f"Borrador mitin barrial #{i + 1}",
                defaults={
                    "event_type": types_by_code["MITIN"],
                    "start_at": start,
                    "end_at": end,
                    "address": "Cancha barrial",
                    "latitude": lat,
                    "longitude": lng,
                    "organizer_name": "Coordinación territorial",
                    "organizer_phone": "0988000000",
                    "responsible": user,
                    "expected_attendees": 150,
                    "objective": "Concentración del cierre territorial.",
                    "created_by": user,
                },
            )
            events_made += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Eventos: {events_made} procesados (total {PoliticalAgendaEvent.objects.count()})"
            )
        )
        self.stdout.write(self.style.SUCCESS("✔ Siembra de political_agenda completa."))
