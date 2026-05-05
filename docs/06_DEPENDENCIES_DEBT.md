# Deuda técnica de dependencias

Este documento registra las dependencias que conviene vigilar o
reemplazar. Es informativo: no exige acción inmediata, pero la deuda
debe revisarse en cada upgrade de Django.

## `django-fsm` 2.8 — sin mantenimiento

`django-fsm` es el motor de transiciones de campañas
(`apps/campaigns/workflows.py`), agenda política
(`apps/political_agenda/workflows.py`) y publicidad territorial
(`apps/territorial_ads/workflows.py`). Lo usa también el `ChangeStateView`
genérico de `apps/workflows/views.py`.

**Riesgo actual**: el último release es de 2021. La librería sigue
funcionando con Django 4.2 LTS, pero no hay parches de seguridad ni
soporte oficial para Django 5.x. Cuando hagamos el upgrade a 5.2 LTS
(probablemente 2026Q3 con Python 3.13), `django-fsm` puede romperse.

**Opciones evaluadas**

| Opción | Esfuerzo | Notas |
|---|---|---|
| Quedarse en `django-fsm` 2.8 | 0 | Funciona en 4.2; revaluar antes de cada upgrade |
| Migrar a `viewflow.fsm` | Medio (1 sprint) | Fork mantenido, API casi 1:1 con `@transition` |
| Migrar a `django-fsm-2` | Bajo | Fork comunitario, drop-in replacement |
| Reescribir con un módulo propio | Alto | No vale la pena, los workflows son estables |

**Decisión**: mantener `django-fsm` 2.8 mientras estemos en Django 4.2 LTS.
Cuando se planifique el upgrade a Django 5.2 LTS, re-evaluar y migrar a
`django-fsm-2` (drop-in) o `viewflow.fsm` según el estado de cada fork.

## `gmcm-django-superadmin` 2.0.10 / `gmcm-django-tracing` 2.0.2

Paquetes privados publicados en PyPI. Sin auditoría externa.
Recomendable en algún momento:

- Mover el código a este monorepo como apps internas (más control,
  cambios atómicos).
- O al menos publicar el repo upstream y enlazarlo desde el README para
  que cualquier mantenedor futuro pueda contribuir.

## `django-ckeditor` 6.7

Mantenimiento esporádico. CKEditor 4 (que es lo que vendorea) está EOL
desde 2023. Si aparece un requisito GDPR / accesibilidad, evaluar
TinyMCE 6 o `django-tiptap`.

## Otras

- `django-notifications-hq` 1.8 — mantenimiento ligero. Aceptable.
- `xhtml2pdf` y `weasyprint` conviven en el `Pipfile`. Decidir cuál es
  el motor canónico (`weasyprint` es más fiel) y eliminar el otro.
- `Pipfile.lock` no está versionado. Generar y commitear:
  ```bash
  pipenv lock
  git add Pipfile.lock
  ```
  Sin lockfile las builds no son reproducibles.

## Plan de upgrade Django 5.2 LTS

Pre-requisitos antes de empezar:

1. CI verde (Bloque 3 ✅).
2. Cobertura ≥ 50 % (hoy <5 %; añadir tests por dominio).
3. Decidir destino de `django-fsm` (ver arriba).
4. Verificar compatibilidad de `django-tenants` 3.x con Django 5.2.

Pasos:

1. `pipenv install django~=5.2`.
2. `python manage.py check --deploy` y arreglar warnings.
3. Correr `django-upgrade --target-version 5.2 .` (ya en pre-commit).
4. Migrar `index_together` → `Meta.indexes` si quedaba alguno.
5. Smoke test en staging contra al menos 2 tenants.
