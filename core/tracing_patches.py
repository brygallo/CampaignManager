"""Multi-tenant fix for ``gmcm-django-tracing``.

Upstream caches ``TracingMiddleware.rules`` as a **class attribute** computed
at import time. In a ``django-tenants`` deployment that import happens before
any tenant is active, so the snapshot is taken against the ``public`` schema
— which contains no ``Rule`` rows. Every later request, regardless of
tenant, then sees an empty rules dict and the ``post_save`` / ``post_delete``
signals never create ``Trace`` rows.

We monkey-patch ``TracingMiddleware.get_rule_by_classname`` to load and
cache rules **per schema** in thread-local storage, refreshing whenever
the active ``connection.schema_name`` changes. The original ``cls.rules``
class attribute is no longer consulted, so the upstream signal handlers
in ``tracing.signals`` automatically inherit the fix without further
patching (they call ``TracingMiddleware.get_rule_by_classname(...)`` and
get the freshly loaded per-tenant dict).
"""
from threading import local

from django.db import connection

from tracing.middleware import TracingMiddleware
from tracing.services import TraceService

_per_thread = local()


def _get_rule_by_classname_per_tenant(cls, classname):
    """Drop-in replacement for the upstream classmethod."""
    schema = getattr(connection, "schema_name", "_default") or "_default"
    cached_schema = getattr(_per_thread, "schema", None)
    if cached_schema != schema:
        _per_thread.rules = TraceService.load_rules()
        _per_thread.schema = schema
    return _per_thread.rules.get(classname.lower())


def _reload_rules_per_tenant(cls):
    """Refresh the cache on the current thread + schema.

    Used by the ``post_save`` / ``post_delete`` Rule signals upstream, which
    expect the cache to refresh whenever a Rule is added or removed.
    """
    schema = getattr(connection, "schema_name", "_default") or "_default"
    _per_thread.rules = TraceService.load_rules()
    _per_thread.schema = schema


def install():
    """Replace the upstream classmethods. Idempotent."""
    if getattr(TracingMiddleware, "_cm_tenant_aware", False):
        return
    TracingMiddleware.get_rule_by_classname = classmethod(
        _get_rule_by_classname_per_tenant
    )
    TracingMiddleware.reload_rules = classmethod(_reload_rules_per_tenant)
    TracingMiddleware._cm_tenant_aware = True


install()
