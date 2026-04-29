# CampaignManager

Multi-site campaign management system built on top of the generic
infrastructure pulled from the `sim` project. Reuses
[`gmcm-django-superadmin`](https://pypi.org/project/gmcm-django-superadmin/)
for declarative CRUD, [`gmcm-django-tracing`](https://pypi.org/project/gmcm-django-tracing/)
for change auditing, [`django-fsm`](https://pypi.org/project/django-fsm/) for
state transitions, and the **Maxton — Vertical Menu Light Theme** (Bootstrap
5.3.1) for the UI.

UI strings are in Spanish; code comments are in English.

---

## Stack

- **Python 3.12** / **Django 4.2 LTS**
- **PostgreSQL 15** (primary database)
- **Redis 7** (cache only — no Celery/RabbitMQ)
- **DRF 3.15** for the API layer
- **django-fsm 2.8** + custom `apps/workflows` for state machines
- **Bootstrap 5.3.1** + Maxton vertical-menu light theme
- File uploads: local filesystem (`media/`) — no S3/MinIO

---

## Repository layout

```
CampaignManager/
├── manage.py
├── Pipfile · Dockerfile · docker-compose.yml · entrypoint.sh
├── menu.yaml                  # Sidebar tree
├── pytest.ini · .env.example
│
├── core/                      # Project core (ex sim/sim/)
│   ├── settings/{base,development,production,test}.py
│   ├── urls.py · wsgi.py · asgi.py
│   ├── base.py                # BaseSite (Spanish URL suffixes + Maxton templates)
│   ├── audit.py               # AuditContextMixin + build_processed_traces
│   ├── list_mixins.py         # WorkflowStateFilterMixin
│   ├── tenancy.py             # ActiveSiteMiddleware + helpers
│   ├── context_processors.py  # active_site, available_sites, brand
│   └── forms.py · widgets.py · validators.py · notifications.py · select2.py · views.py · mixins.py
│
├── apps/
│   ├── authentication/        # Custom User + Profile + login
│   ├── sites_mgmt/            # Site, Domain, SiteMembership (soft multi-tenancy)
│   ├── insoles/               # Inline AJAX forms/details for any registered model
│   └── workflows/             # FSM engine (Workflow, ChangeStateView, …)
│
├── api/                       # DRF v1
│
├── templates/
│   ├── base/                  # base.html, base_list.html, base_form.html, …
│   ├── audit/timeline.html
│   ├── widgets/ · detail_widgets/
│   ├── registration/login.html
│   └── errors/{403,404,500}.html
│
├── static/                    # Maxton bundle (assets/, sass/, plugins/)
└── plantilla/maxton/dist/     # HTML demo for reference (not served)
```

Each Django app keeps its own `migrations/` directory (per-app, versioned in
git — no centralized `dbmigrations/`).

---

## Architectural highlights

- **Declarative CRUD**: register any model with `@register("app.Model")` on a
  `ModelSite` subclass and you instantly get list/create/update/detail/delete
  pages with Maxton styling, breadcrumbs, pagination, search, filters and
  permission checks.
- **Auditing**: every model change (configured via `tracing.Rule`) is recorded
  as a `Trace` with user, IP, OS and a JSON diff. `AuditContextMixin` renders
  the timeline in any DetailView.
- **State machines**: `apps/workflows` ships the FSM engine. Domain models
  declare a `Workflow` (an enum subclass) and methods decorated with
  `@transition(...)`; the UI exposes them through `ChangeStateView`.
- **Soft multi-tenancy**: `Site` is the central entity. Users belong to one or
  more sites via `SiteMembership` and switch the active site from the header.
  `ActiveSiteMiddleware` exposes `request.active_site` and `SiteScopedModel`
  scopes any model to a site.
- **Theme switcher**: `data-bs-theme="light"` by default; a built-in offcanvas
  switches between `light`, `blue-theme`, `dark`, `semi-dark`, `bordered`.

---

## Run with Docker (recommended)

Prerequisites: Docker Desktop installed (`docker --version` should work).

### First-time setup

```bash
cd /Users/usuario/gad/CampaignManager

# 1. Build the image (5–10 min the first time)
docker compose build

# 2. Start Postgres + Redis in the background
docker compose up -d postgres redis

# 3. Initial migrations
docker compose run --rm app python manage.py makemigrations authentication sites_mgmt
docker compose run --rm app python manage.py migrate

# 4. Create the first superuser
docker compose run --rm app python manage.py createsuperuser

# 5. Start the app
docker compose up app
```

Open **http://localhost:8000** and log in with the superuser you just created.

### Day-to-day

```bash
# Tail logs
docker compose logs -f app

# Restart only the app after a code change
docker compose restart app

# Open a shell inside the container
docker compose exec app bash

# Django shell
docker compose exec app python manage.py shell

# Generate / apply migrations
docker compose exec app python manage.py makemigrations <app>
docker compose exec app python manage.py migrate

# Stop everything (keeps the database)
docker compose down

# Stop and wipe the database
docker compose down -v
```

### Rebuild when dependencies change

If you edit `Pipfile`:

```bash
docker compose build app
docker compose up app
```

---

## Run without Docker (host machine)

```bash
cd /Users/usuario/gad/CampaignManager

# 1. Virtualenv with Python 3.12
python3.12 -m venv venv && source venv/bin/activate
pip install --upgrade pip pipenv
pipenv install --dev --skip-lock

# 2. Copy env template and point it to your local services
cp .env.example .env
# Edit .env so DATABASE_URL points at localhost (not "postgres")
# and REDIS_URL at localhost (not "redis").

# 3. Migrations + superuser
python manage.py makemigrations authentication sites_mgmt
python manage.py migrate
python manage.py createsuperuser

# 4. Start the dev server
python manage.py runserver
```

---

## Common issues

| Issue | Cause | Fix |
|---|---|---|
| `port 5432 already in use` | Local Postgres is running | `brew services stop postgresql` or change the host port to `5433:5432` in `docker-compose.yml` |
| `port 8000 already in use` | Another dev server | Change to `8001:8000` |
| `Pipfile.lock not found` | Stale Docker layer | `docker compose build --no-cache app` |
| CSRF error on login | Cookie domain mismatch | Use `http://localhost:8000`, not `127.0.0.1` |
| Static files 404 | `static/` directory empty | Make sure the Maxton bundle is at `static/assets/`, `static/sass/`, `static/plugins/` |

---

## Useful URLs

| URL | Purpose |
|---|---|
| `/` | Dashboard |
| `/login/` | Login |
| `/admin/` | Django admin |
| `/<app>/<model>/listar/` | Generic list view (superadmin) |
| `/<app>/<model>/crear/` | Create form |
| `/<app>/<model>/<pk>/` | Detail |
| `/<app>/<model>/<pk>/editar/` | Edit form |
| `/<app>/<model>/<pk>/eliminar/` | Delete confirmation |
| `/api/v1/` | REST API |
| `/select2/fields/auto.json` | Select2 autocomplete endpoint |

---

## Adding a new model — quick recipe

1. Create the model under `apps/<app>/models.py`. Inherit from
   `tracing.models.BaseModel` to get `created_user/modified_user/...` for free.
2. Optionally inherit from `apps.sites_mgmt.mixins.SiteScopedModel` to scope
   the model to a `Site`.
3. Build a `ModelForm` in `apps/<app>/forms.py` (subclass
   `superadmin.forms.ModelForm` to use `Meta.fieldsets`).
4. Register a `ModelSite` in `apps/<app>/sites.py`:

   ```python
   from superadmin.decorators import register
   from core.base import BaseSite
   from .forms import MyModelForm

   @register("<app>.MyModel")
   class MyModelSite(BaseSite):
       form_class = MyModelForm
       list_fields = ("name", "site", "is_active:Activo")
       detail_fields = {"General": (("name", "site"), ("description",))}
       filter_fields = ("site", "is_active")
       search_params = ("name__icontains",)
   ```

5. Add an entry to `menu.yaml` so the sidebar shows it.
6. Run `python manage.py makemigrations` + `migrate`.

That's it — list, create, update, detail and delete URLs are generated
automatically.

---

## License

Internal project.
