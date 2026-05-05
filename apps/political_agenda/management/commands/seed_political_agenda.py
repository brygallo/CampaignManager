"""Siembra solicitudes de agenda política y eventos en distintos estados.

Genera ~12 solicitudes (PENDING / IN_REVIEW / APPROVED / REJECTED) y ~8
eventos (DRAFT / SCHEDULED / DONE) ligados a la campaña activa.

Uso:
    python manage.py tenant_command seed_political_agenda --schema=<tenant>

Requiere previamente:
    seed_campaigns, seed_sectors
"""
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.campaigns.models import Campaign
from apps.locations.models import Canton, Parish, Province, Sector
from apps.political_agenda.models import (
    AgendaEventType,
    PoliticalAgendaEvent,
    PoliticalAgendaRequest,
)


User = get_user_model()


REQUESTS = [
    # (title, type, priority, requester, org, state)
    ("Reunión con dirigentes barriales La Loma",   "REUNION",      "MEDIA",   "Carlos Tankamash",         "Comité barrial La Loma",            "APPROVED"),
    ("Visita a feria de productores Macas",        "VISITA",       "ALTA",    "Asociación Agroproductora", "Asociación de Productores Morona", "APPROVED"),
    ("Recorrido casa por casa Yantzaza",           "RECORRIDO",    "MEDIA",   "Equipo de campaña",         "Movimiento territorial",           "PENDING"),
    ("Mitin en parque central Sevilla Don Bosco",  "MITIN",        "ALTA",    "Federación Shuar",          "FICSH local",                       "IN_REVIEW"),
    ("Entrevista Radio La Voz del Upano",          "ENTREVISTA",   "ALTA",    "Mario Naichap",             "Radio La Voz del Upano",            "APPROVED"),
    ("Rueda de prensa propuesta vial",             "RUEDA_PRENSA", "URGENTE", "Coordinadora de prensa",   "Equipo de campaña",                 "APPROVED"),
    ("Reunión con docentes UEP Don Bosco",         "REUNION",      "MEDIA",   "Mariana Sharup",            "UEP Don Bosco",                     "PENDING"),
    ("Visita comunidad Tunants",                   "VISITA",       "MEDIA",   "Síndico Wisuma",            "Centro Tunants",                    "PENDING"),
    ("Mitin cierre semana 1",                      "MITIN",        "ALTA",    "Equipo de campaña",         "Movimiento territorial",            "REJECTED"),
    ("Recorrido feria del 9 de Octubre",           "RECORRIDO",    "BAJA",    "Comité 9 de Octubre",       "Comité barrial",                    "PENDING"),
    ("Reunión con transportistas urbanos",         "REUNION",      "ALTA",    "Cooperativa San Cristóbal", "Coop. de transportes",              "IN_REVIEW"),
    ("Visita Centro de Salud General Proaño",      "VISITA",       "MEDIA",   "Dra. Rocío Vargas",         "MSP - Subcentro",                   "APPROVED"),
]


def _at(days_from_now: int, hour: int = 9, minute: int = 0):
    base = timezone.localtime() + timedelta(days=days_from_now)
    return base.replace(hour=hour, minute=minute, second=0, microsecond=0)


class Command(BaseCommand):
    help = "Siembra solicitudes y eventos de agenda política."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Borra eventos y solicitudes antes de sembrar.")

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts.get("reset"):
            PoliticalAgendaEvent.objects.all().delete()
            PoliticalAgendaRequest.objects.all().delete()
            self.stdout.write(self.style.WARNING("Datos previos borrados."))

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

        province = Province.objects.filter(code="14").first()
        canton = Canton.objects.filter(code="1401").first()
        parishes = list(Parish.objects.filter(canton=canton)) if canton else []
        sectors_by_parish = {p.id: list(Sector.objects.filter(parish=p)) for p in parishes}

        # solicitudes
        wf_req = PoliticalAgendaRequest.workflow
        target_state = {
            "PENDING": wf_req.PENDING,
            "IN_REVIEW": wf_req.IN_REVIEW,
            "APPROVED": wf_req.APPROVED,
            "REJECTED": wf_req.REJECTED,
        }
        approved_requests = []
        for i, (title, etype, priority, requester, org, state) in enumerate(REQUESTS):
            parish = parishes[i % len(parishes)] if parishes else None
            sectors = sectors_by_parish.get(parish.id, []) if parish else []
            sector = sectors[i % len(sectors)] if sectors else None

            req, created = PoliticalAgendaRequest.objects.get_or_create(
                campaign=campaign,
                title=title,
                defaults={
                    "event_type": etype,
                    "priority": priority,
                    "requester_name": requester,
                    "requester_phone": f"09{60000000 + i * 11111}",
                    "requester_email": f"{requester.split()[0].lower()}@example.ec",
                    "organization": org,
                    "proposed_start_at": _at(7 + i, hour=9 + (i % 6), minute=0),
                    "proposed_end_at":   _at(7 + i, hour=11 + (i % 6), minute=0),
                    "province": province,
                    "canton": canton,
                    "parish": parish,
                    "sector": sector,
                    "address": "Por confirmar",
                    "objective": "Coordinar agenda territorial.",
                    "expected_attendees": 20 + (i * 7) % 80,
                    "created_by": user,
                },
            )
            # mover a estado deseado vía transiciones FSM
            if req.state == wf_req.PENDING:
                if state == "IN_REVIEW":
                    req.send_to_review(user=user)
                    req.save()
                elif state == "APPROVED":
                    req.approve(user=user)
                    req.save()
                elif state == "REJECTED":
                    req.reject(user=user, rejection_reason="Cruce de agenda con otro evento priorizado.")
                    req.save()
            if req.state == wf_req.APPROVED:
                approved_requests.append(req)

        self.stdout.write(self.style.SUCCESS(f"Solicitudes: {PoliticalAgendaRequest.objects.count()}"))

        # eventos: 4 SCHEDULED desde solicitudes aprobadas, 2 DONE pasadas, 2 DRAFT futuras
        wf_evt = PoliticalAgendaEvent.workflow
        events_made = 0
        # SCHEDULED a partir de solicitudes aprobadas
        for i, req in enumerate(approved_requests[:4]):
            evt, created = PoliticalAgendaEvent.objects.get_or_create(
                campaign=campaign,
                source_request=req,
                title=req.title,
                defaults={
                    "event_type": req.event_type,
                    "start_at": req.proposed_start_at or _at(10 + i, 9),
                    "end_at": req.proposed_end_at or _at(10 + i, 11),
                    "province": req.province,
                    "canton": req.canton,
                    "parish": req.parish,
                    "sector": req.sector,
                    "address": req.address or "Centro Macas",
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
            evt, _c = PoliticalAgendaEvent.objects.get_or_create(
                campaign=campaign,
                title=f"Evento histórico Macas #{i + 1}",
                defaults={
                    "event_type": AgendaEventType.RECORRIDO,
                    "start_at": start,
                    "end_at": end,
                    "province": province,
                    "canton": canton,
                    "parish": parishes[i] if parishes else None,
                    "address": "Centro de la parroquia",
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
            evt, _c = PoliticalAgendaEvent.objects.get_or_create(
                campaign=campaign,
                title=f"Borrador mitin barrial #{i + 1}",
                defaults={
                    "event_type": AgendaEventType.MITIN,
                    "start_at": start,
                    "end_at": end,
                    "province": province,
                    "canton": canton,
                    "parish": parishes[(i + 2) % len(parishes)] if parishes else None,
                    "address": "Cancha barrial",
                    "organizer_name": "Coordinación territorial",
                    "organizer_phone": "0988000000",
                    "responsible": user,
                    "expected_attendees": 150,
                    "objective": "Concentración del cierre territorial.",
                    "created_by": user,
                },
            )
            events_made += 1

        self.stdout.write(self.style.SUCCESS(f"Eventos: {events_made} procesados (total {PoliticalAgendaEvent.objects.count()})"))
        self.stdout.write(self.style.SUCCESS("✔ Siembra de political_agenda completa."))
