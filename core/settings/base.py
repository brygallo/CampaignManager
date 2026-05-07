"""Base settings shared between development / production / test."""
from pathlib import Path

from environs import Env

# ----- Paths -----
BASE_DIR = Path(__file__).resolve().parent.parent.parent
APPS_DIR = BASE_DIR / "apps"

# ----- Env -----
env = Env()
env.read_env(str(BASE_DIR / ".env"), recurse=False)

# SECRET_KEY has no default on purpose: a missing env var must crash at boot
# rather than silently falling back to a known value (which would compromise
# session signing, password reset tokens and CSRF). Override per-env settings
# files (e.g. test.py) supply their own value.
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

# ----- I18N / TZ -----
LANGUAGE_CODE = "es"
TIME_ZONE = "America/Guayaquil"
USE_I18N = True
USE_TZ = True

# ----- Auth -----
AUTH_USER_MODEL = "authentication.User"
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Custom backend allows login with email OR username (case-insensitive email).
AUTHENTICATION_BACKENDS = [
    "apps.authentication.backends.EmailOrUsernameBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# ----- Apps (django-tenants split) -----
# SHARED_APPS live in the "public" schema. Only the tenant registry and the
# bare minimum Django plumbing needed to serve the public landing/signup.
SHARED_APPS = [
    "apps.tenancy",
    "django_tenants",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
]

# TENANT_APPS get a separate copy of their tables inside every tenant schema.
# User, sessions, admin and all domain apps live here so each party is fully
# isolated (its own users, its own permissions, its own data).
TENANT_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.humanize",
    "django.contrib.postgres",
    "superadmin",
    "tracing",
    "django_select2",
    "rest_framework",
    "drf_spectacular",
    "django_filters",
    "corsheaders",
    "mathfilters",
    "ckeditor",
    "notifications",
    "apps.authentication",
    "apps.insoles",
    "apps.workflows",
    "apps.campaigns",
    "apps.locations",
    "apps.territorial_ads",
    "apps.field_surveys",
    "apps.political_agenda",
]

# Django requires a single INSTALLED_APPS list; dedupe shared entries.
INSTALLED_APPS = list(SHARED_APPS) + [a for a in TENANT_APPS if a not in SHARED_APPS]

TENANT_MODEL = "tenancy.Tenant"
TENANT_DOMAIN_MODEL = "tenancy.Domain"
SHOW_PUBLIC_IF_NO_TENANT_FOUND = True

# ----- Middleware -----
# TenantMainMiddleware MUST be first: it resolves request.tenant from the
# host header and switches the connection to the right PostgreSQL schema
# before any other middleware (sessions, auth) touches the DB.
MIDDLEWARE = [
    "django_tenants.middleware.main.TenantMainMiddleware",
    # Path-based fallback: resolves /<slug>/... when the host didn't match a Domain.
    "core.middleware.TenantPathRoutingMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "tracing.middleware.TracingMiddleware",
]

# Tenant URL conf is the existing "core.urls"; the public schema (root domain)
# uses a dedicated, much smaller URL conf for landing + signup + super-admin.
ROOT_URLCONF = "core.urls"
PUBLIC_SCHEMA_URLCONF = "core.urls_public"
WSGI_APPLICATION = "core.wsgi.application"
ASGI_APPLICATION = "core.asgi.application"

# ----- Templates -----
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "superadmin.context_processors.menu",
                "core.context_processors.tenant_path_menu",
                "core.context_processors.brand",
                "core.context_processors.tenant_features",
            ],
            "libraries": {
                # `core` is not in INSTALLED_APPS, so its template tags
                # are registered manually.
                "menu_tags": "core.templatetags.menu_tags",
                "model_meta": "core.templatetags.model_meta",
                "breadcrumbs": "core.templatetags.breadcrumbs",
                "site_urls": "core.templatetags.site_urls",
            },
        },
    },
]

# ----- Database -----
DATABASES = {
    "default": env.dj_db_url(
        "DATABASE_URL",
        default="postgres://campaignmanager:campaignmanager@localhost:5432/campaignmanager",
    ),
}
# Override the engine parsed from DATABASE_URL: django-tenants needs its own
# backend that injects "SET search_path" on every connection checkout.
DATABASES["default"]["ENGINE"] = "django_tenants.postgresql_backend"

# Ensures migrations run only in the schema where the app belongs
# (SHARED_APPS in public, TENANT_APPS in tenant schemas).
DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)

# ----- Static / Media -----
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Django 4.2+: use STORAGES dict instead of DEFAULT_FILE_STORAGE / STATICFILES_STORAGE.
STORAGES = {
    "default": {
        "BACKEND": "core.storage.TenantFileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# ----- Cache (Redis) -----
# KEY_FUNCTION prefixes every key with the active tenant schema so two
# tenants cannot read each other's cached values (Select2 results, view
# fragments, etc.). See core/cache.py.
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/1")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_FUNCTION": "core.cache.tenant_cache_key",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    },
}

# ----- Email -----
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=1025)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@campaignmanager.local")

# ----- Headers / CORS -----
X_FRAME_OPTIONS = "SAMEORIGIN"
# CORS is opt-in: allow-all is only useful while iterating locally. Production
# should enumerate trusted origins via CORS_ALLOWED_ORIGINS.
CORS_ORIGIN_ALLOW_ALL = env.bool("CORS_ORIGIN_ALLOW_ALL", default=False)
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["GET", "OPTIONS", "PATCH", "POST", "PUT", "DELETE"]

# ----- DRF -----
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "user": "1000/hour",
        "anon": "100/hour",
    },
    # Versioning is enforced via the URL prefix (/api/v1/...). Bumping to
    # v2 means a parallel URL include — never mutate v1 in place.
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ("v1",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "CampaignManager API",
    "DESCRIPTION": "API REST multipartido. Cada tenant accede solo a los datos de su schema.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# ----- Select2 -----
# Metronic ya empaqueta Select2 dentro de plugins.bundle.{js,css},
# así que dejamos vacíos los assets propios de django-select2 para evitar 404.
SELECT2_CACHE_BACKEND = "default"
SELECT2_CSS = ""
SELECT2_JS = ""

# ----- Superadmin (user-facing strings + widget templates) -----
BREADCRUMB_HOME_TEXT = "Inicio"
BREADCRUMB_CREATE_TEXT = "Crear"
BREADCRUMB_UPDATE_TEXT = "Editar"
BREADCRUMB_DETAIL_TEXT = ""
BREADCRUMB_DELETE_TEXT = "Eliminar"

BOOLEAN_YES = "Sí"
BOOLEAN_NO = "No"

TEMPLATE_WIDGETS = {
    "text": "widgets/textinput.html",
    "textarea": "widgets/textinput.html",
    "file": "widgets/imageinput.html",
    "clearablefile": "widgets/imageinput.html",
    "checkbox": "widgets/checkboxinput.html",
    "select": "widgets/selectinput.html",
    "date": "widgets/dateinput.html",
    "datetime": "widgets/datetimeinput.html",
    "select2": "widgets/selectinput.html",
    "modelselect2": "widgets/selectinput.html",
    "modelselect2multiple": "widgets/selectinput.html",
    "costtypeselect2": "widgets/selectinput.html",
    "email": "widgets/textinput.html",
    "number": "widgets/textinput.html",
    "password": "widgets/textinput.html",
    "ckeditor": "widgets/ckeditorinput.html",
    "leafletmap": "widgets/textinput.html",
}

TEMPLATE_WIDGETS_DETAIL = {
    "default": "detail_widgets/textinput.html",
    "BooleanField": "detail_widgets/boolean.html",
    "TextField": "detail_widgets/textarea.html",
    "ForeignKey": "detail_widgets/foreignkey.html",
    "OneToOneField": "detail_widgets/foreignkey.html",
    "FileField": "detail_widgets/file.html",
    "ImageField": "detail_widgets/image.html",
    "MultipleChoiceField": "detail_widgets/multiplechoicefield.html",
    "DateField": "detail_widgets/dateinput.html",
    "DateTimeField": "detail_widgets/datetimeinput.html",
    "TimeField": "detail_widgets/datetimeinput.html",
    "IntegerField": "detail_widgets/numberinput.html",
    "BigIntegerField": "detail_widgets/numberinput.html",
    "PositiveIntegerField": "detail_widgets/numberinput.html",
    "SmallIntegerField": "detail_widgets/numberinput.html",
    "DecimalField": "detail_widgets/numberinput.html",
    "FloatField": "detail_widgets/numberinput.html",
}

# ----- CKEditor -----
CKEDITOR_CONFIGS = {
    "default": {
        "toolbar": "full",
        "height": 200,
        "width": "100%",
    },
}

# ----- Notifications -----
DJANGO_NOTIFICATIONS_CONFIG = {
    "USE_JSONFIELD": True,
}

# ----- Branding (consumed by base.html) -----
DEFAULT_THEME = "light"  # light | dark | system
BRAND_NAME = "Control de Campaña"
BRAND_ICON = "assets/img/control-campana.svg"
