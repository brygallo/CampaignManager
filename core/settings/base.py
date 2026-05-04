"""Base settings shared between development / production / test."""
from pathlib import Path

from environs import Env

# ----- Paths -----
BASE_DIR = Path(__file__).resolve().parent.parent.parent
APPS_DIR = BASE_DIR / "apps"

# ----- Env -----
env = Env()
env.read_env(str(BASE_DIR / ".env"), recurse=False)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="change-me-in-production")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["*"])

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

# ----- Apps -----
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.postgres",
]

THIRD_PARTY_APPS = [
    "superadmin",
    "tracing",
    "django_select2",
    "rest_framework",
    "django_filters",
    "corsheaders",
    "mathfilters",
    "ckeditor",
    "notifications",
]

LOCAL_APPS = [
    "apps.authentication",
    "apps.insoles",
    "apps.workflows",
    "apps.campaigns",
    "apps.territorial_ads",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ----- Middleware -----
MIDDLEWARE = [
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

ROOT_URLCONF = "core.urls"
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
                "core.context_processors.brand",
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

# ----- Static / Media -----
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Django 4.2+: use STORAGES dict instead of DEFAULT_FILE_STORAGE / STATICFILES_STORAGE.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ----- Cache (Redis) -----
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/1")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
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
CORS_ORIGIN_ALLOW_ALL = env.bool("CORS_ORIGIN_ALLOW_ALL", default=True)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["GET", "OPTIONS", "PATCH", "POST", "PUT", "DELETE"]

# ----- DRF -----
REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
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
    "file": "widgets/textinput.html",
    "clearablefile": "widgets/textinput.html",
    "checkbox": "widgets/checkboxinput.html",
    "select": "widgets/selectinput.html",
    "date": "widgets/dateinput.html",
    "datetime": "widgets/datetimeinput.html",
    "select2": "widgets/textinput.html",
    "modelselect2": "widgets/textinput.html",
    "modelselect2multiple": "widgets/textinput.html",
    "email": "widgets/textinput.html",
    "number": "widgets/textinput.html",
    "ckeditor": "widgets/ckeditorinput.html",
}

TEMPLATE_WIDGETS_DETAIL = {
    "default": "detail_widgets/textinput.html",
    "BooleanField": "detail_widgets/boolean.html",
    "TextField": "detail_widgets/textarea.html",
    "ForeignKey": "detail_widgets/foreignkey.html",
    "OneToOneField": "detail_widgets/foreignkey.html",
    "FileField": "detail_widgets/file.html",
    "ImageField": "detail_widgets/file.html",
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
