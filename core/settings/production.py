"""Production settings."""
from .base import *  # noqa: F401,F403

DEBUG = False

# Defense in depth: refuse to start a production process if anything else in
# the import chain (env override, monkey patch) has set DEBUG truthy. A
# debug-on prod leaks the URLconf and stack traces, so we crash loudly at
# boot instead of serving.
assert not DEBUG, "DEBUG must remain False in production settings."

# ALLOWED_HOSTS in base.py defaults to []. Empty + DEBUG=False makes Django
# reject every request — surface the misconfig in CI/staging instead of
# silently 400ing users in production.
assert ALLOWED_HOSTS, (  # noqa: F405
    "DJANGO_ALLOWED_HOSTS must be set in production. "
    "Provide a comma-separated list of hostnames via the environment."
)

# ----- Security -----
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# Trust X-Forwarded-Proto from the upstream proxy (nginx / load balancer) so
# request.is_secure() is correct and SECURE_SSL_REDIRECT does not loop.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=True)  # noqa: F405
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=True)  # noqa: F405
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # CSRF token must be readable by JS
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)  # noqa: F405
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Static files are collected to the S3/MinIO bucket via ``core.storage.StaticS3Storage``.
STORAGES["staticfiles"]["BACKEND"] = "core.storage.StaticS3Storage"  # noqa: F405

# ----- Content Security Policy -----
# Initially deployed in report-only mode so we can collect violations from
# Metronic's inline scripts/styles before enforcing. Flip
# CSP_REPORT_ONLY to False once the inline JS in templates/ has been moved
# to static files (Bloque 7 follow-up).
INSTALLED_APPS = [*INSTALLED_APPS, "csp"]  # noqa: F405
MIDDLEWARE.append("csp.middleware.CSPMiddleware")  # noqa: F405

CSP_REPORT_ONLY = True
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://fonts.googleapis.com")
CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com", "data:")
CSP_IMG_SRC = ("'self'", "data:", "blob:")
CSP_CONNECT_SRC = ("'self'",)
CSP_FRAME_ANCESTORS = ("'self'",)
CSP_BASE_URI = ("'self'",)
CSP_FORM_ACTION = ("'self'",)

# Cached template loader.
TEMPLATES[0]["OPTIONS"]["loaders"] = [  # noqa: F405
    (
        "django.template.loaders.cached.Loader",
        [
            "django.template.loaders.filesystem.Loader",
            "django.template.loaders.app_directories.Loader",
        ],
    ),
]
TEMPLATES[0].pop("APP_DIRS", None)  # noqa: F405

# ----- Logging -----
# Inject the active tenant schema into every record so log aggregators can
# slice by party. Format is plain text because production usually pipes stderr
# to a JSON-aware shipper (Loki/Promtail, Vector, Fluent Bit).
import logging

from django.db import connection


class TenantContextFilter(logging.Filter):
    def filter(self, record):
        record.tenant = getattr(connection, "schema_name", "-") or "-"
        return True


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "tenant": {"()": "core.settings.production.TenantContextFilter"},
    },
    "formatters": {
        "default": {
            "format": "%(asctime)s %(levelname)s [%(tenant)s] %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["tenant"],
            "formatter": "default",
        },
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
