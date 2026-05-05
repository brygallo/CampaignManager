# Sprint 1 — Multi-tenancy con `django-tenants`

Sprint inicial de la migración a SaaS multi-partido. Cada tenant (partido
político) recibe su propio schema PostgreSQL con datos, usuarios, permisos
y sesiones aislados. Solo el registro de tenants vive en el schema `public`.

## Cambios aplicados en este sprint

1. `Pipfile`: añadido `django-tenants ~= 3.7`.
2. `apps/tenancy/`: nueva app con modelos `Tenant`, `Domain`,
   `TenantBranding` (todos en `SHARED_APPS`). `TenantSettings` (feature
   flags por módulo) se introducirá en la Fase 5 cuando llegue el menú
   dinámico. Incluye migración inicial versionada.
3. `core/settings/base.py`:
   - Reorganización de apps en `SHARED_APPS` y `TENANT_APPS`.
   - `ENGINE` cambiado a `django_tenants.postgresql_backend`.
   - `DATABASE_ROUTERS` añade `TenantSyncRouter`.
   - `TenantMainMiddleware` + `TenantPathRoutingMiddleware` insertados al
     inicio del MIDDLEWARE.
   - `TENANT_MODEL`, `TENANT_DOMAIN_MODEL`, `PUBLIC_SCHEMA_URLCONF`.
4. `core/urls_public.py`: nuevo URL conf mínimo para el schema `public`.
5. `core/middleware.py`: `TenantPathRoutingMiddleware` para modo path
   (tudominio.com/<slug>/...).

## Modalidades de acceso por tenant

Cada tenant puede acceder por **cualquiera** de estas tres formas (las
configura el operador al crear el `Domain` o al elegir el slug):

### A. Dominio propio  `mipartido.com`

Para clientes premium con DNS propio. El registro `Domain` apunta al host
exacto. Cookies y sesión totalmente aisladas. Requiere certificado SSL
propio.

```python
Domain.objects.create(domain="mipartido.com", tenant=t, is_primary=True)
```

### B. Subdominio  `pk.tudominio.com`

Estándar para la mayoría de partidos. Requiere DNS wildcard `*.tudominio.com`
y certificado SSL wildcard. Cookies aisladas por subdominio.

```python
Domain.objects.create(domain="pk.tudominio.com", tenant=t, is_primary=True)
```

### C. Path en el dominio raíz  `tudominio.com/pk/...`  (modo trial / demo)

No requiere DNS adicional. El primer segmento del path identifica al tenant
por su `slug`. **Las cookies y sesión se comparten entre tenants del mismo
dominio raíz** — no recomendado para clientes que requieren aislamiento
fuerte. Implementado por `core.middleware.TenantPathRoutingMiddleware`.

No hace falta crear un `Domain`; basta con que el `Tenant.slug` exista y
el tenant esté `is_active=True`.

| Atributo | Modo A (dominio propio) | Modo B (subdominio) | Modo C (path) |
|---|---|---|---|
| URL ejemplo | `mipartido.com/campaigns/` | `pk.tudominio.com/campaigns/` | `tudominio.com/pk/campaigns/` |
| DNS necesario | Apuntar dominio al servidor | Wildcard `*.tudominio.com` | Ninguno |
| Cert SSL | Propio | Wildcard | Único compartido |
| Aislamiento cookies | Total | Total | **Compartido** |
| Recomendado para | Clientes premium | Mayoría | Trial / demo |

## Reparto de apps

`User` vive en `TENANT_APPS`: cada partido gestiona sus propios usuarios.
Un mismo correo puede registrarse en partidos distintos sin colisión.

```
SHARED_APPS (schema "public")
  apps.tenancy
  django_tenants
  django.contrib.contenttypes
  django.contrib.staticfiles

TENANT_APPS (un schema por partido)
  django.contrib.admin / auth / contenttypes / sessions / messages /
  humanize / postgres
  superadmin, tracing, django_select2, rest_framework, django_filters,
  corsheaders, mathfilters, ckeditor, notifications
  apps.authentication, apps.insoles, apps.workflows, apps.campaigns,
  apps.locations, apps.territorial_ads, apps.field_surveys,
  apps.political_agenda
```

## Pasos para activar Sprint 1 en local

> Estos pasos asumen que ya hay datos productivos en la BD. Si trabajas con
> una BD vacía, salta a "BD vacía" más abajo.

### 0. Backup obligatorio

```bash
pg_dump -h localhost -U campaignmanager campaignmanager \
  > backups/pre-tenants-$(date +%F-%H%M).sql
```

### 1. Instalar dependencia

```bash
pipenv install
```

### 2. Verificar migraciones de la app de tenancy

La migración inicial de `tenancy` ya está incluida en el repo. Usa este
comando solo para verificar que no quedaron cambios de modelo sin migración:

```bash
python manage.py makemigrations --check --dry-run
```

### 3a. Caso A — BD existente con datos productivos

Un único comando hace todo: rename del schema, creación del nuevo `public`,
migración de SHARED_APPS, e inserción del tenant + dominio + branding.

```bash
# Primero verifica con --dry-run qué va a hacer:
python manage.py migrate_to_multitenant \
  --slug partido-default \
  --name "Partido por defecto" \
  --domain partido-default.localhost \
  --dry-run

# Si todo se ve bien, ejecuta de verdad:
python manage.py migrate_to_multitenant \
  --slug partido-default \
  --name "Partido por defecto" \
  --domain partido-default.localhost
```

Argumentos del comando:

| Flag | Obligatorio | Para qué |
|---|---|---|
| `--slug` | Sí | URL-friendly id; también base del schema PG (los `-` se convierten a `_`). |
| `--name` | Sí | Nombre del partido (lo que ven los usuarios). |
| `--domain` | No | Host primario para Modo A/B. Omítelo si solo usarás Modo C (path). |
| `--brand-name` | No | Texto de branding. Por defecto = `--name`. |
| `--dry-run` | No | Imprime lo que haría sin tocar la BD. |

Validaciones que hace antes de ejecutar:
- El schema activo debe ser `public`.
- `tenancy_tenant` NO debe existir aún (idempotencia: aborta si ya migraste).
- El schema destino (ej. `partido_default`) NO debe existir.
- `campaigns_campaign` SÍ debe existir en `public` (verifica que hay datos
  reales que migrar).

### 3b. Caso B — BD vacía / nuevo entorno

```bash
python manage.py migrate_schemas --shared
python manage.py create_tenant \
  --slug partido-demo \
  --name "Partido Demo" \
  --domain partido-demo.localhost \
  --owner-username admin \
  --owner-email admin@partido-demo.localhost \
  --owner-password "cambia-esto"
```

`create_tenant` crea el schema desde cero, corre las migraciones de
`TENANT_APPS` y opcionalmente crea un superusuario dentro.

### 4. (Solo Caso A) Crear superusuario en el tenant

```bash
python manage.py tenant_command createsuperuser --schema=partido_default
```

### 5. Probar acceso

Edita `/etc/hosts`:

```
127.0.0.1 partido-default.localhost
127.0.0.1 partido-demo.localhost
```

Levanta el servidor:

```bash
python manage.py runserver 0.0.0.0:8000
```

- `http://localhost:8000/` → landing público (`urls_public`).
- `http://partido-default.localhost:8000/` → app del partido vía
  subdominio (Modo B).
- `http://localhost:8000/partido-default/` → app del partido vía path
  (Modo C). Sirve para probar sin DNS local.

## Comandos útiles del día a día

| Comando | Para qué |
|---|---|
| `migrate_to_multitenant --slug X --name Y` | **One-shot**: convierte un DB single-tenant en multi-tenant. |
| `create_tenant --slug X --name Y [--domain ...] [--owner-* ...]` | Da de alta un partido nuevo (schema desde cero). |
| `migrate_schemas --shared` | Migra solo `public`. |
| `migrate_schemas --tenant` | Migra todos los tenants. |
| `migrate_schemas --schema=slug` | Migra un tenant específico. |
| `tenant_command shell --schema=slug` | Shell apuntando al schema del tenant. |
| `tenant_command createsuperuser --schema=slug` | Crea admin en un tenant. |

## Riesgos conocidos a vigilar

1. **`makemigrations`** corre contra `public`: si una app de `TENANT_APPS`
   genera migraciones no detectadas, ejecutar `makemigrations <app>` por
   nombre.
2. **`tracing.middleware.TracingMiddleware`** ahora corre dentro del schema
   del tenant, así que su tabla de auditoría queda aislada por partido.
   Verificar que no intente escribir en `public`.
3. **`superadmin` package**: sus URLs se montan en `core/urls.py` (URL conf
   del tenant). Si registra modelos de `tenancy`, se romperá — verificar
   que no auto-descubra apps de `SHARED_APPS`.
4. **Conexiones**: si hay pgbouncer en `transaction` mode, `SET search_path`
   puede perderse entre transacciones. `django-tenants` lo emite por
   conexión, no por transacción. Recomendado pgbouncer en `session` mode
   o nada de pooler externo en local.

## Estado de las fases

| Fase | Descripción | Estado |
|---|---|---|
| 1 | django-tenants instalado, modelos, settings, middleware | ✅ |
| 2 | Migración productiva (`migrate_to_multitenant`) | Listo para ejecutar |
| 3 | Branding dinámico (`TenantBranding`) | ✅ |
| 4 | Storage por tenant (`TenantFileSystemStorage`) | ✅ |
| 5 | `TenantSettings` (feature flags) + menú dinámico | ✅ |
| 6 | Onboarding público (signup en `urls_public`) | Pendiente |
| 7 | Panel super-admin global | Pendiente — ver nota abajo |
| 8 | Auditoría cross-tenant agregada | Pendiente |
| 9 | Planes / cuotas | Pendiente |
| 10 | DNS wildcard / deploy | Pendiente |

### Nota sobre Fase 7 — modelo `SuperAdmin`

El panel global (en `core/urls_public.py`) requiere autenticación
**fuera** del schema de cualquier tenant. Hoy `User` vive en `TENANT_APPS`,
por lo que `request.user` es `AnonymousUser` cuando se navega por el
dominio raíz: no hay tabla `auth_user` en `public`.

La solución correcta es introducir un modelo separado `SuperAdmin` (o
`PlatformOperator`) en `apps.tenancy` (que ya está en `SHARED_APPS`):

```python
class SuperAdmin(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    USERNAME_FIELD = "email"
```

Luego un backend de auth separado que solo valide contra esa tabla
**solo** cuando el schema activo sea `public`, y un par de vistas
protegidas en `urls_public.py` para listar / crear tenants y editar
`TenantSettings` y `TenantBranding`. Es una pieza grande (auth, vistas,
templates) y conviene atacarla en su propio sprint cuando la Fase 6
(onboarding) esté clara.

Mientras tanto, las altas de tenant se hacen vía `manage.py create_tenant`.

## Sprint 2 — Migración productiva

Mismo `migrate_to_multitenant` corrido contra la BD productiva, con backup
verificado, y con `--dry-run` previo. Pasos en producción:

1. Anunciar ventana de mantenimiento (5-10 min).
2. Detener workers / procesos que escriben en la BD.
3. `pg_dump` completo + verificar que el dump abre.
4. `pipenv install` (django-tenants + dependencias).
5. `python manage.py makemigrations tenancy`.
6. `python manage.py migrate_to_multitenant --slug ... --name ... --domain ... --dry-run`.
7. Si todo se ve bien: ejecutar sin `--dry-run`.
8. Configurar DNS / vhost para el dominio del tenant (si aplica).
9. Smoke test: login como admin, crear una campaña de prueba, verificar
   que aparece dentro del tenant y NO en `public`.
10. Reactivar workers.

Rollback: restaurar el `pg_dump` del paso 3.
