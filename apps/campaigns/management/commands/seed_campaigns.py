"""Siembra catálogos y campañas de prueba con datos plausibles de
Ecuador, con foco en el cantón Morona (Macas) — provincia de Morona Santiago.

Los nombres de candidatos son sintéticos (mezcla de antropónimos comunes
mestizos y shuar de la zona) — NO corresponden a personas reales.
Los movimientos políticos sí existen y están registrados ante el CNE.

Uso:
    python manage.py seed_campaigns           # idempotente (get_or_create)
    python manage.py seed_campaigns --reset   # borra todo y resiembra
"""
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.campaigns.models import (
    Campaign,
    Candidate,
    Election,
    PoliticalMovement,
    Position,
)


# ---------------- catálogos ----------------

ELECTIONS = [
    {
        "name": "Elecciones Seccionales 2023",
        "election_date": date(2023, 2, 5),
        "description": (
            "Elección de prefectos, alcaldes, concejales urbanos y rurales, "
            "y vocales de juntas parroquiales rurales (5 de febrero de 2023)."
        ),
    },
    {
        "name": "Elecciones Generales Anticipadas 2023",
        "election_date": date(2023, 8, 20),
        "description": (
            "Comicios convocados tras la 'muerte cruzada' decretada por el "
            "Presidente Guillermo Lasso (1ª vuelta 20-ago-2023, 2ª vuelta "
            "15-oct-2023)."
        ),
    },
    {
        "name": "Elecciones Generales 2025",
        "election_date": date(2025, 2, 9),
        "description": (
            "Elecciones presidenciales, vicepresidenciales, asambleístas "
            "nacionales, provinciales y parlamentarios andinos "
            "(1ª vuelta 9-feb-2025, balotaje 13-abr-2025)."
        ),
    },
    {
        "name": "Elecciones Seccionales 2027",
        "election_date": date(2027, 2, 7),
        "description": (
            "Próximo proceso seccional: prefectos, alcaldes, concejales y "
            "vocales de junta parroquial."
        ),
    },
]

MOVEMENTS = [
    {"name": "Acción Democrática Nacional",     "acronym": "ADN",   "list_number": "7",  "color": "#1E4DB7"},
    {"name": "Revolución Ciudadana",            "acronym": "RC",    "list_number": "5",  "color": "#1AAE52"},
    {"name": "Partido Social Cristiano",        "acronym": "PSC",   "list_number": "6",  "color": "#E40521"},
    {"name": "Pachakutik",                      "acronym": "PK",    "list_number": "18", "color": "#F4B400"},
    {"name": "CREO",                            "acronym": "CREO",  "list_number": "21", "color": "#003594"},
    {"name": "Construye",                       "acronym": "CONST", "list_number": "25", "color": "#16A085"},
    {"name": "Izquierda Democrática",           "acronym": "ID",    "list_number": "12", "color": "#D81B60"},
    {"name": "SUMA",                            "acronym": "SUMA",  "list_number": "23", "color": "#FF6F00"},
    {"name": "Centro Democrático",              "acronym": "CD",    "list_number": "1",  "color": "#5E35B1"},
    {"name": "Avanza",                          "acronym": "AVZ",   "list_number": "8",  "color": "#00897B"},
    {"name": "Sociedad Patriótica",             "acronym": "PSP",   "list_number": "3",  "color": "#C62828"},
    {"name": "Unidad Popular",                  "acronym": "UP",    "list_number": "2",  "color": "#B71C1C"},
]

POSITIONS = [
    # Nacionales
    {"name": "Presidente de la República",                "scope": "nacional"},
    {"name": "Vicepresidente de la República",            "scope": "nacional"},
    {"name": "Asambleísta Nacional",                      "scope": "nacional"},
    {"name": "Parlamentario Andino",                      "scope": "nacional"},
    # Provinciales
    {"name": "Prefecto de Morona Santiago",               "scope": "provincial"},
    {"name": "Viceprefecto de Morona Santiago",           "scope": "provincial"},
    {"name": "Asambleísta por Morona Santiago",           "scope": "provincial"},
    # Cantonales (Cantón Morona — capital Macas)
    {"name": "Alcalde del cantón Morona",                 "scope": "cantonal"},
    {"name": "Concejal Urbano del cantón Morona",         "scope": "cantonal"},
    {"name": "Concejal Rural del cantón Morona",          "scope": "cantonal"},
    # Parroquiales (parroquias rurales del cantón Morona)
    {"name": "Presidente Junta Parroquial Sevilla Don Bosco", "scope": "parroquial"},
    {"name": "Presidente Junta Parroquial San Isidro",        "scope": "parroquial"},
    {"name": "Presidente Junta Parroquial General Proaño",    "scope": "parroquial"},
]

# Nombres sintéticos plausibles para la región amazónica ecuatoriana
# (mezcla mestiza + shuar). Cédulas inventadas con dígito verificador
# inválido a propósito (acaban en 9) para evitar parecerse a reales.
CANDIDATES = [
    ("María Tsamaraint Wajai",     "1400123459", "maria.tsamaraint@example.ec",   "07 270 0011"),
    ("Carlos Alberto Rivadeneira", "1400234569", "carlos.rivadeneira@example.ec", "07 270 0022"),
    ("Esthela Naichap Pujupat",    "1400345679", "esthela.naichap@example.ec",    "07 270 0033"),
    ("Luis Fernando Calle Ortiz",  "1400456789", "luis.calle@example.ec",         "07 270 0044"),
    ("Karina Zhunio Vargas",       "1400567899", "karina.zhunio@example.ec",      "07 270 0055"),
    ("Patricio Antún Chiriap",     "1400678999", "patricio.antun@example.ec",     "07 270 0066"),
    ("Diego Espinoza Maldonado",   "1400789999", "diego.espinoza@example.ec",     "07 270 0077"),
    ("Rocío Tankamash Jimpikit",   "1400890999", "rocio.tankamash@example.ec",    "07 270 0088"),
    ("Jorge Vinicio Andrade",      "1400910999", "jorge.andrade@example.ec",      "07 270 0099"),
    ("Sandra Tunki Awananch",      "1401010999", "sandra.tunki@example.ec",       "07 270 0110"),
    ("Edwin Oswaldo Patiño",       "1401110999", "edwin.patino@example.ec",       "07 270 0121"),
    ("Mariana Sharup Pinchupá",    "1401210999", "mariana.sharup@example.ec",     "07 270 0132"),
    ("Andrés Sebastián Cobo",      "1401310999", "andres.cobo@example.ec",        "07 270 0143"),
    ("Verónica Wisuma Tiwi",       "1401410999", "veronica.wisuma@example.ec",    "07 270 0154"),
    ("Hernán Patricio Tello",      "1401510999", "hernan.tello@example.ec",       "07 270 0165"),
]

# (campaign_name, election, candidate, movement, position, start, end, state)
CAMPAIGNS = [
    # Seccionales 2023 — Macas / Morona Santiago
    ("Macas Avanza",                "Elecciones Seccionales 2023", "Carlos Alberto Rivadeneira", "ADN",
     "Alcalde del cantón Morona", date(2022, 11, 1), date(2023, 2, 5), "CLOSED"),
    ("Mujer y Territorio",          "Elecciones Seccionales 2023", "Esthela Naichap Pujupat", "PK",
     "Prefecto de Morona Santiago", date(2022, 11, 1), date(2023, 2, 5), "CLOSED"),
    ("Construyamos Morona",         "Elecciones Seccionales 2023", "Luis Fernando Calle Ortiz", "PSC",
     "Concejal Urbano del cantón Morona", date(2022, 11, 1), date(2023, 2, 5), "CLOSED"),

    # Generales anticipadas 2023
    ("Voz Amazónica al Pleno",      "Elecciones Generales Anticipadas 2023", "Patricio Antún Chiriap", "PK",
     "Asambleísta por Morona Santiago", date(2023, 6, 1), date(2023, 8, 20), "CLOSED"),

    # Generales 2025 (cerradas)
    ("Ecuador con Esperanza",       "Elecciones Generales 2025", "Diego Espinoza Maldonado", "RC",
     "Asambleísta Nacional", date(2024, 11, 1), date(2025, 4, 13), "CLOSED"),
    ("Pachakutik 2025 — Bloque",    "Elecciones Generales 2025", "Rocío Tankamash Jimpikit", "PK",
     "Asambleísta por Morona Santiago", date(2024, 12, 1), date(2025, 4, 13), "CLOSED"),

    # Seccionales 2027 — en preparación / activas
    ("Macas para Todos",            "Elecciones Seccionales 2027", "María Tsamaraint Wajai", "RC",
     "Alcalde del cantón Morona", date(2026, 9, 1), date(2027, 2, 7), "ACTIVE"),
    ("Renovar la Prefectura",       "Elecciones Seccionales 2027", "Karina Zhunio Vargas", "ID",
     "Prefecto de Morona Santiago", date(2026, 9, 1), date(2027, 2, 7), "ACTIVE"),
    ("Sevilla en Marcha",           "Elecciones Seccionales 2027", "Sandra Tunki Awananch", "PK",
     "Presidente Junta Parroquial Sevilla Don Bosco", date(2026, 10, 1), date(2027, 2, 7), "ACTIVE"),
    ("Morona Joven 2027",           "Elecciones Seccionales 2027", "Andrés Sebastián Cobo", "CONST",
     "Concejal Urbano del cantón Morona", date(2026, 10, 15), date(2027, 2, 7), "DRAFT"),
    ("San Isidro Renace",           "Elecciones Seccionales 2027", "Edwin Oswaldo Patiño", "SUMA",
     "Presidente Junta Parroquial San Isidro", date(2026, 11, 1), date(2027, 2, 7), "DRAFT"),
    ("Por una Asamblea Local",      "Elecciones Seccionales 2027", "Mariana Sharup Pinchupá", "PSC",
     "Concejal Rural del cantón Morona", date(2026, 11, 1), date(2027, 2, 7), "DRAFT"),
]


# ---------------- command ----------------

class Command(BaseCommand):
    help = "Siembra catálogos y campañas de prueba (Ecuador / cantón Morona — Macas)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Borra todas las campañas, candidatos, elecciones, movimientos y cargos antes de sembrar.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts.get("reset"):
            self.stdout.write(self.style.WARNING("Borrando datos previos..."))
            Campaign.objects.all().delete()
            Candidate.objects.all().delete()
            Election.objects.all().delete()
            PoliticalMovement.objects.all().delete()
            Position.objects.all().delete()

        # --- catálogos ---
        elections = {e["name"]: Election.objects.get_or_create(name=e["name"], defaults=e)[0] for e in ELECTIONS}
        self.stdout.write(self.style.SUCCESS(f"Elecciones: {len(elections)}"))

        movements = {m["acronym"]: PoliticalMovement.objects.get_or_create(name=m["name"], defaults=m)[0] for m in MOVEMENTS}
        self.stdout.write(self.style.SUCCESS(f"Movimientos: {len(movements)}"))

        positions = {p["name"]: Position.objects.get_or_create(name=p["name"], defaults=p)[0] for p in POSITIONS}
        self.stdout.write(self.style.SUCCESS(f"Cargos: {len(positions)}"))

        candidates = {}
        for name, ident, email, phone in CANDIDATES:
            obj, _ = Candidate.objects.get_or_create(
                identification=ident,
                defaults={"full_name": name, "email": email, "phone": phone},
            )
            candidates[name] = obj
        self.stdout.write(self.style.SUCCESS(f"Candidatos: {len(candidates)}"))

        # --- campañas ---
        # importamos workflow para mapear nombres → enteros
        from apps.campaigns.workflows import CampaignWorkflow
        wf = CampaignWorkflow()
        state_map = {
            "DRAFT": wf.DRAFT.value,
            "ACTIVE": wf.ACTIVE.value,
            "CLOSED": wf.CLOSED.value,
            "CANCELED": wf.CANCELED.value,
        }

        created = 0
        for (cname, ename, cand_name, mov_acr, pos_name, start, end, state) in CAMPAIGNS:
            obj, was_created = Campaign.objects.get_or_create(
                election=elections[ename],
                candidate=candidates[cand_name],
                position=positions[pos_name],
                defaults={
                    "name": cname,
                    "movement": movements[mov_acr],
                    "start_date": start,
                    "end_date": end,
                    "state": state_map[state],
                },
            )
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(
            f"Campañas: {created} nuevas (total {Campaign.objects.count()})"
        ))

        self.stdout.write(self.style.SUCCESS("✔ Siembra completa."))
