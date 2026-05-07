"""Siembra publicidad territorial en distintos estados del workflow.

Genera ~14 lonas/vallas/afiches con avance gradual por el flujo:
OFRECIDA → APROBADA → PENDIENTE_INSTALACION → INSTALADA → DANADA / RETIRADA

Uso:
    python manage.py tenant_command seed_territorial_ads --schema=<tenant>

Requiere previamente: seed_campaigns
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
from apps.field_surveys.models import AdvertisingType
from apps.territorial_ads.models import PhysicalAdvertisement


User = get_user_model()

LAT_BASE = Decimal("-2.310")
LON_BASE = Decimal("-78.120")


# (type, w, h, address, owner, phone, target_state)
ADS = [
    ("lona",  Decimal("4.00"), Decimal("2.00"),
     "Vía Macas-Puyo km 1, predio del Sr. Calle",     "Sr. Mario Calle",      "0991111111", "INSTALADA"),
    ("lona",  Decimal("3.00"), Decimal("1.50"),
     "Av. 13 de Abril junto a panadería La Espiga",  "Doña Rocío Vargas",    "0992222222", "INSTALADA"),
    ("valla", Decimal("8.00"), Decimal("4.00"),
     "Redondel del avión, Av. 29 de Mayo",           "Coop. San Cristóbal",  "0993333333", "PENDIENTE_INSTALACION"),
    ("lona",  Decimal("2.00"), Decimal("1.00"),
     "Plaza 9 de Octubre frente a iglesia",          "Comité 9 de Octubre",  "0994444444", "APROBADA"),
    ("afiche", None,          None,
     "Tienda La Loma, Calle Soasti",                 "Sra. Carmen Sharup",   "0995555555", "INSTALADA"),
    ("lona",  Decimal("3.50"), Decimal("1.80"),
     "Ingreso a Sevilla DB, vía principal",          "Síndico Wisuma",       "0996666666", "DANADA"),
    ("lona",  Decimal("2.50"), Decimal("1.20"),
     "Frente a parque central General Proaño",      "GAD Parroquial Proaño","0997777777", "INSTALADA"),
    ("valla", Decimal("6.00"), Decimal("3.00"),
     "Av. Amazonas y Bolívar",                       "Inmobiliaria Sangay",  "0998888888", "OFRECIDA"),
    ("afiche", None,          None,
     "Restaurante El Upano, calle Cuenca",           "Sr. Patricio Tello",   "0999999999", "OFRECIDA"),
    ("lona",  Decimal("2.50"), Decimal("1.20"),
     "Calle Riobamba, barrio Yantzaza",              "Doña Mariana Sharup",  "0990000001", "RETIRADA"),
    ("lona",  Decimal("3.00"), Decimal("1.50"),
     "San Isidro centro, casa del Sr. Naichap",      "Sr. Edwin Naichap",    "0990000002", "APROBADA"),
    ("valla", Decimal("8.00"), Decimal("4.00"),
     "Vía Macas-Sucúa km 5",                         "Hostal Río Upano",     "0990000003", "PENDIENTE_INSTALACION"),
    ("lona",  Decimal("2.50"), Decimal("1.20"),
     "Calle Quito, barrio La Florida",               "Sr. Hugo Wisuma",      "0990000004", "INSTALADA"),
    ("afiche", None,          None,
     "Peluquería Centro, calle Sucre",               "Sra. Verónica Pinchupá","0990000005", "INSTALADA"),
]


def _make_image_bytes() -> bytes:
    img = Image.new("RGB", (240, 180), color=(220, 230, 250))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    return buf.getvalue()


def _jitter(base: Decimal, spread: float = 0.02) -> Decimal:
    return base + Decimal(str(random.uniform(-spread, spread))).quantize(Decimal("0.000001"))


class Command(BaseCommand):
    help = "Siembra publicidad territorial en varios estados."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Borra publicidad existente antes de sembrar.")

    @transaction.atomic
    def handle(self, *args, **opts):
        random.seed(7)

        if opts.get("reset"):
            PhysicalAdvertisement.objects.all().delete()
            self.stdout.write(self.style.WARNING("Datos previos borrados."))

        campaign = (
            Campaign.objects.filter(name="Macas para Todos").first()
            or Campaign.objects.filter(state__gt=0).order_by("-start_date").first()
        )
        user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if user is None:
            self.stderr.write(self.style.ERROR("No hay usuarios."))
            return

        types_by_code = {t.code: t for t in AdvertisingType.objects.filter(is_active=True)}
        wf = PhysicalAdvertisement.workflow
        created = 0
        for i, (atype, w, h, address, owner, phone, target) in enumerate(ADS):
            advertisement_type = types_by_code.get(atype.upper()) or types_by_code.get("AFICHE")
            if advertisement_type is None:
                self.stderr.write(self.style.ERROR("Primero carga los tipos de publicidad."))
                return

            ad, was_created = PhysicalAdvertisement.objects.get_or_create(
                address=address,
                defaults={
                    "campaign": campaign,
                    "advertisement_type": advertisement_type,
                    "quantity": 1,
                    "width_meters": w,
                    "height_meters": h,
                    "owner_name": owner,
                    "owner_phone": phone,
                    "offered_notes": "Acepta colocación durante toda la campaña.",
                    "address": address,
                    "reference": "Coordenadas referenciales aproximadas",
                    "offered_latitude": _jitter(LAT_BASE),
                    "offered_longitude": _jitter(LON_BASE),
                },
            )
            if was_created:
                created += 1

            # avanzar workflow hasta el estado objetivo
            self._advance_to(ad, target, user, wf)

        self.stdout.write(self.style.SUCCESS(
            f"Publicidad: {created} nuevas (total {PhysicalAdvertisement.objects.count()})."
        ))

    def _advance_to(self, ad, target, user, wf):
        target_value = getattr(wf, target)
        # secuencia OFRECIDA → APROBADA → PENDIENTE_INSTALACION → INSTALADA → DANADA → RETIRADA
        order = [
            (wf.OFRECIDA, None),
            (wf.APROBADA, "approve"),
            (wf.PENDIENTE_INSTALACION, "assign_installation"),
            (wf.INSTALADA, "mark_installed"),
            (wf.DANADA, "report_damage"),
            (wf.RETIRADA, "retire"),
        ]
        target_idx = next(i for i, (s, _) in enumerate(order) if s == target_value)

        for state, method in order[1:target_idx + 1]:
            # ya alcanzó (o pasó) este estado en una corrida previa
            if ad.state >= state:
                continue
            if method == "approve":
                ad.approve(
                    user=user,
                    width_meters=ad.width_meters,
                    height_meters=ad.height_meters,
                    installation_instructions=(
                        "Se requiere escalera y dos personas para colocación segura."
                    ),
                )
            elif method == "assign_installation":
                ad.assign_installation(user=user, installer_team="Brigada Macas A")
            elif method == "mark_installed":
                ad.mark_installed(
                    user=user,
                    installation_photo=ContentFile(
                        _make_image_bytes(), name=f"install_{ad.pk}.jpg"
                    ),
                    installed_latitude=ad.offered_latitude,
                    installed_longitude=ad.offered_longitude,
                    installation_notes="Instalación con permiso del dueño. Buen estado.",
                )
            elif method == "report_damage":
                ad.report_damage(
                    user=user,
                    damage_notes="Lona rasgada por viento fuerte; requiere reposición.",
                )
            elif method == "retire":
                ad.retire(
                    user=user,
                    retirement_notes="Retirada al cierre del periodo electoral.",
                )
            ad.save()
