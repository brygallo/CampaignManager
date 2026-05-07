"""Siembra levantamientos de campo, competidores y detecciones de
publicidad de competencia para campañas activas.

Coordenadas centradas en Macas (Morona Santiago):
    lat ~ -2.31, lon ~ -78.12

Uso:
    python manage.py tenant_command seed_field_surveys --schema=<tenant>

Requiere previamente:
    seed_campaigns, seed_field_survey_results
"""
import io
import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from PIL import Image

from apps.campaigns.models import Campaign
from apps.field_surveys.models import (
    AdvertisingType,
    Competitor,
    CompetitorAdvertisingDetection,
    FieldSurvey,
    SurveyResultOption,
)


User = get_user_model()

LAT_BASE = Decimal("-2.310")
LON_BASE = Decimal("-78.120")

PERSON_NAMES = [
    "Juan Carlos Pérez", "María Elena Tankamash", "Pedro Antonio López",
    "Rosa Beatriz Naichap", "Hugo Wisuma Tiwi", "Carmen Lucía Pinchupá",
    "Manuel Andrés Calle", "Ana Patricia Sharup", "Luis Eduardo Vargas",
    "Sandra Liliana Mejía", "Jorge Luis Antún", "Verónica Tsamaraint",
    "Diego Armando Ortiz", "Mariana Isabel Zhunio", "Edwin Chiriap Wajai",
    "Patricia Esperanza Rivadeneira", "Roberto Tunki Awananch",
    "Gladys Margarita Sharup", "Jaime Vinicio Andrade", "Cecilia Tankamash",
    "Fernando Benigno Cobo", "Daniela Sharup Pinchupá", "Wilson Naichap",
    "Mónica Yajaira Calle", "Galo Patricio Tello",
]

NOTES = [
    "Promete asistir a la próxima reunión barrial.",
    "Pidió no recibir más visitas.",
    "Se comprometió a difundir mensaje en el barrio.",
    "Familia con 5 votantes hábiles.",
    "Solicita ayuda con tema de servicios básicos.",
    "Sin novedad, casa cerrada.",
    "Ya tiene definido su voto.",
    "Apoyará si se incluye obra de su sector.",
    "Pidió material publicitario.",
    "Líder informal del sector, contactar nuevamente.",
    "",
]

COMPETITORS = [
    ("RC", "5", "Revolución Ciudadana", "Fausto Tankamash R.", "#1AAE52"),
    ("ADN", "7", "Acción Democrática Nacional", "Bryan Calle Ortiz", "#1E4DB7"),
    ("PSC", "6", "Partido Social Cristiano", "Mauricio Antún", "#E40521"),
    ("ID", "12", "Izquierda Democrática", "Estela Naichap", "#D81B60"),
    ("SUMA", "23", "SUMA", "Patricia Vargas", "#FF6F00"),
    ("CREO", "21", "CREO", "Hernán Chiriap", "#003594"),
]


def _make_image_bytes(label: str) -> bytes:
    img = Image.new("RGB", (240, 180), color=(245, 240, 230))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    return buf.getvalue()


def _jitter(base: Decimal, spread: float = 0.02) -> Decimal:
    return base + Decimal(str(random.uniform(-spread, spread))).quantize(Decimal("0.000001"))


class Command(BaseCommand):
    help = "Siembra levantamientos de campo, competidores y detecciones."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Borra detecciones, levantamientos y competidores antes de sembrar.",
        )
        parser.add_argument(
            "--surveys",
            type=int,
            default=30,
            help="Cantidad de levantamientos a generar (default: 30).",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        random.seed(42)

        if opts.get("reset"):
            CompetitorAdvertisingDetection.objects.all().delete()
            FieldSurvey.objects.all().delete()
            Competitor.objects.all().delete()
            self.stdout.write(self.style.WARNING("Datos previos borrados."))

        campaign = (
            Campaign.objects.filter(name="Macas para Todos").first()
            or Campaign.objects.filter(state__gt=0).order_by("-start_date").first()
        )
        if campaign is None:
            self.stderr.write(self.style.ERROR(
                "No hay campaña disponible. Corre primero seed_campaigns."
            ))
            return

        brigadier = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if brigadier is None:
            self.stderr.write(self.style.ERROR("No hay usuarios. Crea uno antes de sembrar."))
            return

        competitors = []
        for _, list_no, org, candidate, color in COMPETITORS:
            obj, _created = Competitor.objects.get_or_create(
                campaign=campaign,
                list_number=list_no,
                political_organization=org,
                defaults={"candidate_name": candidate, "color": color},
            )
            competitors.append(obj)
        self.stdout.write(self.style.SUCCESS(f"Competidores: {len(competitors)}"))

        result_options = list(SurveyResultOption.objects.filter(is_active=True))
        result_priority = {
            "APOYA": 0.45, "INDECISO": 0.20, "NO_APOYA": 0.10,
            "ATENDIO": 0.15, "NO_ATENDIO": 0.10,
        }
        priority_pool = []
        for code, weight in result_priority.items():
            priority_pool.extend([code] * int(weight * 100))

        ad_types = list(AdvertisingType.objects.filter(is_active=True))

        n = opts["surveys"]
        surveys = []
        for i in range(n):
            person = random.choice(PERSON_NAMES)
            survey = FieldSurvey.objects.create(
                campaign=campaign,
                brigadier=brigadier,
                latitude=_jitter(LAT_BASE),
                longitude=_jitter(LON_BASE),
                gps_accuracy=Decimal(str(round(random.uniform(3, 12), 2))),
                location_was_manually_adjusted=random.random() < 0.15,
                person_name=person,
                person_phone=f"09{random.randint(10000000, 99999999)}",
                voters_count=random.choice([1, 1, 2, 2, 3, 3, 4, 5]),
                notes=random.choice(NOTES),
                created_by=brigadier,
            )
            picked_codes = {random.choice(priority_pool)}
            if random.random() < 0.35:
                picked_codes.add(random.choice(["ACEPTA_PUBLICIDAD", "RECHAZA_PUBLICIDAD", "REQUIERE_SEGUIMIENTO"]))
            survey.results.set([r for r in result_options if r.code in picked_codes])
            surveys.append(survey)
        self.stdout.write(self.style.SUCCESS(f"Levantamientos: {len(surveys)}"))

        detections_created = 0
        if ad_types and competitors:
            for survey in random.sample(surveys, k=min(12, len(surveys))):
                detection = CompetitorAdvertisingDetection(
                    campaign=campaign,
                    competitor=random.choice(competitors),
                    brigadier=brigadier,
                    field_survey=survey if random.random() < 0.7 else None,
                    advertising_type=random.choice(ad_types),
                    latitude=_jitter(survey.latitude, spread=0.001),
                    longitude=_jitter(survey.longitude, spread=0.001),
                    gps_accuracy=Decimal(str(round(random.uniform(4, 15), 2))),
                    location_was_manually_adjusted=random.random() < 0.1,
                    observation=random.choice([
                        "Lona en buen estado, alta visibilidad.",
                        "Afiche reciente, sin daños.",
                        "Sticker pequeño en poste.",
                        "Valla grande junto a la vía principal.",
                        "",
                    ]),
                    created_by=brigadier,
                )
                if random.random() < 0.6:
                    detection.photo.save(
                        f"detection_{survey.pk}.jpg",
                        ContentFile(_make_image_bytes("comp")),
                        save=False,
                    )
                detection.save()
                detections_created += 1
        self.stdout.write(self.style.SUCCESS(f"Detecciones de competencia: {detections_created}"))

        self.stdout.write(self.style.SUCCESS("✔ Siembra de field_surveys completa."))
