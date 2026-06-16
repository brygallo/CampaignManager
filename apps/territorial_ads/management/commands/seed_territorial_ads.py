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
from django.utils import timezone
from PIL import Image

from apps.campaigns.models import Campaign
from apps.field_surveys.models import AdvertisingType
from apps.territorial_ads.models import (
    AdvertisingTypeSize,
    PhysicalAdvertisement,
)


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
        self._seed_sizes(types_by_code)
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
            ad.items.get_or_create(
                advertisement_type=advertisement_type, defaults={"quantity": 1}
            )

            # avanzar workflow hasta el estado objetivo
            self._advance_to(ad, target, user, wf)

        self.stdout.write(self.style.SUCCESS(
            f"Publicidad: {created} nuevas (total {PhysicalAdvertisement.objects.count()})."
        ))

    DEFAULT_SIZES = {
        "LONA": ["Pared", "Cuadro"],
        "VALLA": ["Grande", "Mediana"],
    }

    def _seed_sizes(self, types_by_code):
        """Ensure every active advertising type has a size catalog."""
        for code, ad_type in types_by_code.items():
            names = self.DEFAULT_SIZES.get(code, ["Pequeño", "Mediano", "Grande"])
            for index, name in enumerate(names):
                AdvertisingTypeSize.objects.get_or_create(
                    advertisement_type=ad_type,
                    name=name,
                    defaults={"order": index},
                )

    def _advance_to(self, ad, target, user, wf):
        # Secuencia de la solicitud: OFRECIDA → APROBADA → PENDIENTE →
        # INSTALADA (automático al instalar todas las unidades). DANADA y
        # RETIRADA se gestionan por unidad.
        if target == "OFRECIDA":
            return
        if ad.state == wf.OFRECIDA:
            # Units are materialized at offer time; configure each one
            # (size + instructions) before the request-level approval.
            ad.materialize_units()
            for item in ad.items.all():
                first_size = AdvertisingTypeSize.objects.filter(
                    advertisement_type=item.advertisement_type, is_active=True
                ).order_by("order", "name").first()
                for unit in item.units.all():
                    unit.installation_instructions = (
                        "Se requiere escalera y dos personas para colocación segura."
                    )
                    if first_size:
                        unit.size = first_size
                    unit.save(update_fields=["installation_instructions", "size"])
            ad.approve(user=user)
            ad.save()
        if target == "APROBADA":
            return
        if ad.state == wf.APROBADA:
            # Installer/team are assigned per unit now.
            for item in ad.items.all():
                for unit in item.units.all():
                    if unit.state != unit.workflow.PENDIENTE:
                        continue
                    unit.installer_team = "Brigada Macas A"
                    unit.assigned_by = user
                    unit.assigned_at = timezone.now()
                    unit.save(
                        update_fields=["installer_team", "assigned_by", "assigned_at"]
                    )
            ad.assign_installation(user=user)
            ad.save()
        if target == "PENDIENTE_INSTALACION":
            return
        # Instalar todas las unidades pendientes; al completar la última la
        # solicitud pasa sola a INSTALADA (sync_state_with_units).
        unit_wf = None
        for item in ad.items.all():
            for unit in item.units.all():
                unit_wf = unit.workflow
                if unit.state != unit.workflow.PENDIENTE:
                    continue
                unit.mark_installed(
                    user=user,
                    photo=ContentFile(
                        _make_image_bytes(), name=f"install_{ad.pk}_{unit.pk}.jpg"
                    ),
                    latitude=_jitter(ad.offered_latitude, 0.0005),
                    longitude=_jitter(ad.offered_longitude, 0.0005),
                    notes="Instalación con permiso del dueño. Buen estado.",
                )
                unit.save()
        # ``ad`` quedó desactualizado: el sync guardó otra instancia.
        ad = PhysicalAdvertisement.objects.get(pk=ad.pk)
        if target == "INSTALADA":
            return
        if target == "DANADA":
            unit = next(
                (u for u in ad.units if u.state == unit_wf.INSTALADA), None
            )
            if unit is not None:
                unit.report_damage(
                    user=user,
                    damage_notes="Lona rasgada por viento fuerte; requiere reposición.",
                )
                unit.save()
            return
        if target == "RETIRADA" and ad.state in (wf.INSTALADA, wf.DANADA):
            ad.retire(user=user)
            ad.save()
