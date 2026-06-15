"""Active-campaign middleware, switch view, form mixin, and scope mixin."""
from datetime import timedelta
from unittest.mock import MagicMock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.campaigns import active as active_module
from apps.campaigns.active import (
    ActiveCampaignMiddleware,
    SESSION_ALL_KEY,
    SESSION_KEY,
    can_view_historical_campaigns,
    clear_active_campaign,
    is_campaign_read_only,
    list_available_campaigns,
    resolve_active_campaign,
    scope_queryset_to_active_campaign,
    set_active_campaign,
    visible_campaigns_queryset,
)
from apps.campaigns.models import (
    Campaign,
    Candidate,
    Election,
    PoliticalMovement,
    Position,
)
from apps.campaigns.views import clear_active_campaign_view, switch_active_campaign
from apps.field_surveys.models import FieldSurvey
from core.form_mixins import ActiveCampaignFormMixin
from core.list_mixins import ActiveCampaignScopeMixin


def _make_campaign(name, **overrides):
    election, _ = Election.objects.get_or_create(name=f"E-{name}")
    candidate, _ = Candidate.objects.get_or_create(full_name=f"C-{name}")
    movement, _ = PoliticalMovement.objects.get_or_create(name=f"M-{name}")
    position, _ = Position.objects.get_or_create(name=f"P-{name}")
    data = {
        "name": name,
        "election": election,
        "candidate": candidate,
        "movement": movement,
        "position": position,
        "start_date": (timezone.now() + timedelta(days=1)).date(),
        "end_date": (timezone.now() + timedelta(days=30)).date(),
    }
    data.update(overrides)
    return Campaign.objects.create(**data)


class _FakeTenant:
    schema_name = "test_tenant"


class _RequestBuilder:
    def __init__(self):
        self.factory = RequestFactory()

    def __call__(self, path="/", method="get", **kwargs):
        request = getattr(self.factory, method)(path, **kwargs)
        request.tenant = _FakeTenant()
        request.session = {}
        return request


class ResolveActiveCampaignTests(TestCase):
    def setUp(self):
        self.builder = _RequestBuilder()

    def test_public_schema_returns_none(self):
        from django_tenants.utils import get_public_schema_name

        request = self.builder()
        request.tenant.schema_name = get_public_schema_name()
        self.assertIsNone(resolve_active_campaign(request))

    def test_auto_selects_single_campaign(self):
        only = _make_campaign("Solo")
        request = self.builder()
        resolved = resolve_active_campaign(request)
        self.assertEqual(resolved, only)
        self.assertEqual(request.session[SESSION_KEY], only.pk)

    def test_returns_none_with_no_campaigns(self):
        request = self.builder()
        self.assertIsNone(resolve_active_campaign(request))

    def test_keeps_session_id_when_valid(self):
        first = _make_campaign("Primera")
        second = _make_campaign("Segunda")
        request = self.builder()
        request.session[SESSION_KEY] = second.pk
        resolved = resolve_active_campaign(request)
        self.assertEqual(resolved, second)
        # Session id wasn't replaced with the auto-pick.
        self.assertEqual(request.session[SESSION_KEY], second.pk)
        del first

    def test_drops_stale_id_and_falls_back_to_auto_select(self):
        only = _make_campaign("Solo")
        request = self.builder()
        request.session[SESSION_KEY] = 99_999
        resolved = resolve_active_campaign(request)
        self.assertEqual(resolved, only)
        self.assertEqual(request.session[SESSION_KEY], only.pk)

    def test_does_not_auto_select_with_multiple(self):
        _make_campaign("Una")
        _make_campaign("Dos")
        request = self.builder()
        self.assertIsNone(resolve_active_campaign(request))
        self.assertNotIn(SESSION_KEY, request.session)

    def test_prefers_default_campaign_with_multiple(self):
        _make_campaign("Una")
        favorite = _make_campaign("Favorita", is_default=True)
        _make_campaign("Otra")
        request = self.builder()
        resolved = resolve_active_campaign(request)
        self.assertEqual(resolved, favorite)
        self.assertEqual(request.session[SESSION_KEY], favorite.pk)

    def test_all_mode_blocks_default_autoselect(self):
        _make_campaign("Una")
        _make_campaign("Favorita", is_default=True)
        request = self.builder()
        request.session[SESSION_ALL_KEY] = True
        self.assertIsNone(resolve_active_campaign(request))
        self.assertNotIn(SESSION_KEY, request.session)

    def test_inactive_campaign_is_not_restored_from_session(self):
        inactive = _make_campaign("Inactiva", is_active=False)
        active = _make_campaign("Activa")
        request = self.builder()
        request.session[SESSION_KEY] = inactive.pk
        resolved = resolve_active_campaign(request)
        self.assertEqual(resolved, active)
        self.assertEqual(request.session[SESSION_KEY], active.pk)

    def test_returns_none_when_only_inactive_campaigns_exist(self):
        _make_campaign("Inactiva", is_active=False)
        request = self.builder()
        self.assertIsNone(resolve_active_campaign(request))
        self.assertNotIn(SESSION_KEY, request.session)

    def test_archived_campaign_restored_from_session_with_permission(self):
        archived = _make_campaign("Historica", is_active=False)
        _make_campaign("Operativa")
        user = get_user_model().objects.create_user(
            username="historian", email="historian@example.com", password="x"
        )
        user.user_permissions.add(
            Permission.objects.get(codename="view_historical_campaigns")
        )
        request = self.builder()
        request.user = get_user_model().objects.get(pk=user.pk)
        request.session[SESSION_KEY] = archived.pk
        self.assertEqual(resolve_active_campaign(request), archived)

    def test_auto_select_never_picks_archived_even_with_permission(self):
        # The permission allows *keeping* an archived selection, but the
        # default/single-campaign auto-pick must stay on operational ones.
        _make_campaign("Historica", is_active=False, is_default=True)
        operational = _make_campaign("Operativa")
        user = get_user_model().objects.create_user(
            username="historian2", email="historian2@example.com", password="x"
        )
        user.user_permissions.add(
            Permission.objects.get(codename="view_historical_campaigns")
        )
        request = self.builder()
        request.user = get_user_model().objects.get(pk=user.pk)
        self.assertEqual(resolve_active_campaign(request), operational)


class ActiveCampaignHelpersTests(TestCase):
    def setUp(self):
        self.builder = _RequestBuilder()
        self.user = get_user_model().objects.create_user(
            username="campaign-helper",
            email="campaign-helper@example.com",
            password="x",
        )

    def test_set_active_campaign_clears_all_mode_flag(self):
        campaign = _make_campaign("Activa")
        request = self.builder()
        request.session[SESSION_ALL_KEY] = True
        set_active_campaign(request, campaign)
        self.assertEqual(request.session[SESSION_KEY], campaign.pk)
        self.assertNotIn(SESSION_ALL_KEY, request.session)
        self.assertEqual(request.active_campaign, campaign)

    def test_clear_active_campaign_sets_all_mode_flag(self):
        campaign = _make_campaign("Activa")
        request = self.builder()
        request.session[SESSION_KEY] = campaign.pk
        request.active_campaign = campaign
        clear_active_campaign(request)
        self.assertNotIn(SESSION_KEY, request.session)
        self.assertTrue(request.session[SESSION_ALL_KEY])
        self.assertIsNone(request.active_campaign)

    def test_list_available_campaigns_excludes_inactive(self):
        favorite = _make_campaign("Favorita", is_default=True)
        _make_campaign("Visible")
        _make_campaign("Oculta", is_active=False, is_default=True)
        campaigns = list(list_available_campaigns(self.user))
        self.assertEqual(campaigns[0], favorite)
        self.assertNotIn("Oculta", [campaign.name for campaign in campaigns])

    def test_visible_campaigns_queryset_hides_inactive_without_permission(self):
        visible = _make_campaign("Visible")
        _make_campaign("Historica", is_active=False)
        queryset = visible_campaigns_queryset(Campaign.objects.all(), self.user)
        self.assertEqual(list(queryset), [visible])

    def test_visible_campaigns_queryset_includes_historical_with_permission(self):
        active = _make_campaign("Activa")
        historical = _make_campaign("Historica", is_active=False)
        self.user.user_permissions.add(
            Permission.objects.get(codename="view_historical_campaigns")
        )
        queryset = visible_campaigns_queryset(Campaign.objects.all(), self.user)
        self.assertEqual({campaign.pk for campaign in queryset}, {active.pk, historical.pk})

    def test_can_view_historical_campaigns_checks_permission(self):
        self.assertFalse(can_view_historical_campaigns(self.user))
        self.user.user_permissions.add(
            Permission.objects.get(codename="view_historical_campaigns")
        )
        refreshed = get_user_model().objects.get(pk=self.user.pk)
        self.assertTrue(can_view_historical_campaigns(refreshed))

    def test_list_available_campaigns_includes_archived_with_permission(self):
        operational = _make_campaign("Operativa")
        archived = _make_campaign("Historica", is_active=False)
        self.user.user_permissions.add(
            Permission.objects.get(codename="view_historical_campaigns")
        )
        refreshed = get_user_model().objects.get(pk=self.user.pk)
        campaigns = list(list_available_campaigns(refreshed))
        self.assertEqual({c.pk for c in campaigns}, {operational.pk, archived.pk})
        # Archived campaigns sink below operational ones.
        self.assertEqual(campaigns[-1], archived)

    def test_is_campaign_read_only(self):
        operational = _make_campaign("Operativa2")
        archived = _make_campaign("Archivada2", is_active=False)
        closed = _make_campaign("Cerrada2")
        Campaign.objects.filter(pk=closed.pk).update(state=Campaign.workflow.CLOSED)
        closed = Campaign.objects.get(pk=closed.pk)
        self.assertFalse(is_campaign_read_only(None))
        self.assertFalse(is_campaign_read_only(operational))
        self.assertTrue(is_campaign_read_only(archived))
        self.assertTrue(is_campaign_read_only(closed))


class CampaignDefaultFlagTests(TestCase):
    def test_save_demotes_previous_default(self):
        first = _make_campaign("Una", is_default=True)
        second = _make_campaign("Dos", is_default=True)
        self.assertFalse(Campaign.objects.get(pk=first.pk).is_default)
        self.assertTrue(Campaign.objects.get(pk=second.pk).is_default)

    def test_clearing_default_leaves_no_default(self):
        first = _make_campaign("Una", is_default=True)
        first.is_default = False
        first.save()
        self.assertEqual(Campaign.objects.filter(is_default=True).count(), 0)


class ActiveCampaignMiddlewareTests(TestCase):
    def setUp(self):
        self.builder = _RequestBuilder()

    def test_sets_attribute_on_request(self):
        only = _make_campaign("Única")
        request = self.builder()
        called = {}

        def get_response(req):
            called["active"] = req.active_campaign
            return "ok"

        middleware = ActiveCampaignMiddleware(get_response)
        middleware(request)
        self.assertEqual(called["active"], only)


class SwitchActiveCampaignViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="switcher",
            email="s@example.com",
            password="testpass123",
        )
        self.first = _make_campaign("Primera")
        self.second = _make_campaign("Segunda")

    def _request(self, path, method="post", data=None):
        request = getattr(RequestFactory(), method)(path, data=data or {})
        request.user = self.user
        request.tenant = _FakeTenant()
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))
        return request

    def test_post_sets_session_key_and_redirects(self):
        request = self._request(
            reverse("campaigns:switch_active", args=[self.second.pk]),
            data={"next": "/somewhere/"},
        )
        response = switch_active_campaign(request, self.second.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/somewhere/")
        self.assertEqual(request.session[SESSION_KEY], self.second.pk)

    def test_post_unknown_campaign_returns_404(self):
        request = self._request(reverse("campaigns:switch_active", args=[99_999]))
        with self.assertRaisesMessage(Exception, ""):
            switch_active_campaign(request, 99_999)

    def test_clear_view_removes_session_key(self):
        request = self._request(reverse("campaigns:clear_active"))
        request.session[SESSION_KEY] = self.first.pk
        response = clear_active_campaign_view(request)
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(SESSION_KEY, request.session)
        self.assertTrue(request.session[SESSION_ALL_KEY])

    def test_cannot_switch_to_inactive_campaign(self):
        inactive = _make_campaign("Inactiva", is_active=False)
        request = self._request(reverse("campaigns:switch_active", args=[inactive.pk]))
        with self.assertRaisesMessage(Exception, ""):
            switch_active_campaign(request, inactive.pk)

    def test_can_switch_to_inactive_campaign_with_permission(self):
        inactive = _make_campaign("Inactiva2", is_active=False)
        self.user.user_permissions.add(
            Permission.objects.get(codename="view_historical_campaigns")
        )
        request = self._request(
            reverse("campaigns:switch_active", args=[inactive.pk]),
            data={"next": "/somewhere/"},
        )
        request.user = get_user_model().objects.get(pk=self.user.pk)
        response = switch_active_campaign(request, inactive.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(request.session[SESSION_KEY], inactive.pk)

    def test_safe_next_blocks_external_redirects(self):
        request = self._request(
            reverse("campaigns:switch_active", args=[self.first.pk]),
            data={"next": "https://evil.example.com/path"},
        )
        response = switch_active_campaign(request, self.first.pk)
        # Falls back to home.
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("home"))

    def test_safe_next_blocks_backslash_open_redirect(self):
        # Browsers normalize backslashes to slashes in the path, which would
        # otherwise turn ``/\\evil.com/path`` into a protocol-relative redirect.
        request = self._request(
            reverse("campaigns:switch_active", args=[self.first.pk]),
            data={"next": "/\\evil.com/path"},
        )
        response = switch_active_campaign(request, self.first.pk)
        self.assertEqual(response["Location"], reverse("home"))

    def test_safe_next_downgrades_detail_url_to_list(self):
        # A detail URL is downgraded to its parent list because the record
        # is usually out of scope after a campaign switch.
        request = self._request(
            reverse("campaigns:switch_active", args=[self.first.pk]),
            data={"next": "/political_agenda/politicalagendaevent/42/"},
        )
        response = switch_active_campaign(request, self.first.pk)
        self.assertEqual(response["Location"], "/political_agenda/politicalagendaevent/")

    def test_safe_next_downgrades_edit_url_to_list(self):
        request = self._request(
            reverse("campaigns:switch_active", args=[self.first.pk]),
            data={"next": "/political_agenda/politicalagendaevent/42/editar/"},
        )
        response = switch_active_campaign(request, self.first.pk)
        self.assertEqual(response["Location"], "/political_agenda/politicalagendaevent/")

    def test_safe_next_downgrades_delete_url_to_list(self):
        request = self._request(
            reverse("campaigns:switch_active", args=[self.first.pk]),
            data={"next": "/political_agenda/politicalagendaevent/42/eliminar/"},
        )
        response = switch_active_campaign(request, self.first.pk)
        self.assertEqual(response["Location"], "/political_agenda/politicalagendaevent/")

    def test_safe_next_preserves_querystring_on_downgrade(self):
        # Query (sort, page) is on the LIST surface, so it must survive the
        # downgrade from a detail URL.
        request = self._request(
            reverse("campaigns:switch_active", args=[self.first.pk]),
            data={"next": "/political_agenda/politicalagendaevent/42/?ordering=name"},
        )
        response = switch_active_campaign(request, self.first.pk)
        self.assertEqual(
            response["Location"],
            "/political_agenda/politicalagendaevent/?ordering=name",
        )

    def test_safe_next_keeps_list_url_unchanged(self):
        # A list URL must NOT be downgraded — only detail/edit/delete tails.
        request = self._request(
            reverse("campaigns:switch_active", args=[self.first.pk]),
            data={"next": "/political_agenda/politicalagendaevent/?page=2"},
        )
        response = switch_active_campaign(request, self.first.pk)
        self.assertEqual(
            response["Location"],
            "/political_agenda/politicalagendaevent/?page=2",
        )

    def test_get_is_rejected(self):
        wrapped = switch_active_campaign
        request = self._request(
            reverse("campaigns:switch_active", args=[self.first.pk]),
            method="get",
        )
        response = wrapped(request, self.first.pk)
        self.assertEqual(response.status_code, 405)


class _FakeSite:
    def __init__(self, model, respect_active_campaign=True):
        self.model = model
        self.respect_active_campaign = respect_active_campaign


class _BaseListView:
    def get_queryset(self):
        return self.model.objects.all()


class _FakeListView(ActiveCampaignScopeMixin, _BaseListView):
    def __init__(self, model, request, respect=True):
        self.site = _FakeSite(model, respect_active_campaign=respect)
        self.model = model
        self.request = request


class ScopeMixinTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_noop_when_model_has_no_campaign_fk(self):
        request = self.factory.get("/")
        request.active_campaign = MagicMock(pk=1)
        view = _FakeListView(Election, request)
        # `Election` has no `campaign` FK; queryset is unchanged.
        self.assertEqual(view.get_queryset().count(), Election.objects.count())

    def test_filters_by_active_campaign(self):
        a = _make_campaign("A")
        b = _make_campaign("B")
        user = get_user_model().objects.create_user(
            username="brigadier", password="x"
        )
        s1 = FieldSurvey.objects.create(
            campaign=a,
            brigadier=user,
            latitude="0.0",
            longitude="0.0",
        )
        FieldSurvey.objects.create(
            campaign=b,
            brigadier=user,
            latitude="0.0",
            longitude="0.0",
        )
        request = self.factory.get("/")
        request.active_campaign = a
        view = _FakeListView(FieldSurvey, request)
        qs = view.get_queryset()
        self.assertEqual(list(qs), [s1])

    def test_opt_out_disables_scoping(self):
        a = _make_campaign("A")
        user = get_user_model().objects.create_user(
            username="brigadier2", password="x"
        )
        FieldSurvey.objects.create(
            campaign=a,
            brigadier=user,
            latitude="0.0",
            longitude="0.0",
        )
        # Site disables scoping even though active campaign is set.
        request = self.factory.get("/")
        request.active_campaign = a
        view = _FakeListView(FieldSurvey, request, respect=False)
        self.assertEqual(view.get_queryset().count(), 1)

    def test_scope_helper_is_noop_without_active_campaign(self):
        active_campaign = _make_campaign("A")
        inactive_campaign = _make_campaign("B", is_active=False)
        user = get_user_model().objects.create_user(
            username="brigadier3",
            email="brigadier3@example.com",
            password="x",
        )
        survey = FieldSurvey.objects.create(
            campaign=active_campaign,
            brigadier=user,
            latitude="0.0",
            longitude="0.0",
        )
        FieldSurvey.objects.create(
            campaign=inactive_campaign,
            brigadier=user,
            latitude="1.0",
            longitude="1.0",
        )
        request = self.factory.get("/")
        request.user = user
        request.active_campaign = None
        qs = scope_queryset_to_active_campaign(FieldSurvey.objects.all(), request)
        self.assertEqual(list(qs), [survey])

    def test_scope_helper_in_all_mode_includes_history_with_permission(self):
        active_campaign = _make_campaign("Activa")
        inactive_campaign = _make_campaign("Historica", is_active=False)
        user = get_user_model().objects.create_user(
            username="brigadier-history",
            email="brigadier-history@example.com",
            password="x",
        )
        user.user_permissions.add(
            Permission.objects.get(codename="view_historical_campaigns")
        )
        first = FieldSurvey.objects.create(
            campaign=active_campaign,
            brigadier=user,
            latitude="0.0",
            longitude="0.0",
        )
        second = FieldSurvey.objects.create(
            campaign=inactive_campaign,
            brigadier=user,
            latitude="1.0",
            longitude="1.0",
        )
        request = self.factory.get("/")
        request.user = user
        request.active_campaign = None
        qs = scope_queryset_to_active_campaign(FieldSurvey.objects.all(), request)
        self.assertEqual({item.pk for item in qs}, {first.pk, second.pk})

    def test_scope_helper_is_noop_for_invalid_field(self):
        a = _make_campaign("A")
        user = get_user_model().objects.create_user(username="brigadier4", password="x")
        survey = FieldSurvey.objects.create(
            campaign=a,
            brigadier=user,
            latitude="0.0",
            longitude="0.0",
        )
        request = self.factory.get("/")
        request.active_campaign = a
        qs = scope_queryset_to_active_campaign(
            FieldSurvey.objects.all(), request, field="missing_relation"
        )
        self.assertIn(survey, qs)


class _FakeForm:
    def __init__(self, model):
        from django.forms.models import modelform_factory

        FormCls = modelform_factory(model, fields=["campaign"])
        self.form = FormCls()
        self.fields = self.form.fields


class _BaseCreateView:
    def get_initial(self):
        return {}

    def get_form(self, form_class=None):
        return _FakeForm(self.site.model).form


class _FakeCreateView(ActiveCampaignFormMixin, _BaseCreateView):
    def __init__(self, model, request, respect=True):
        self.site = _FakeSite(model, respect_active_campaign=respect)
        self.request = request


class FormMixinTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_initial_carries_active_campaign(self):
        active = _make_campaign("Activa")
        request = self.factory.get("/")
        request.active_campaign = active
        view = _FakeCreateView(FieldSurvey, request)
        initial = view.get_initial()
        self.assertEqual(initial["campaign"], active.pk)

    def test_form_field_is_restricted_and_hidden(self):
        from django.forms import HiddenInput

        active = _make_campaign("Activa2")
        _make_campaign("Otra")  # would normally appear in the queryset
        request = self.factory.get("/")
        request.active_campaign = active
        view = _FakeCreateView(FieldSurvey, request)
        form = view.get_form()
        field = form.fields["campaign"]
        self.assertEqual(list(field.queryset), [active])
        self.assertIsInstance(field.widget, HiddenInput)
        self.assertEqual(field.initial, active.pk)

    def test_noop_without_active_campaign(self):
        request = self.factory.get("/")
        request.active_campaign = None
        view = _FakeCreateView(FieldSurvey, request)
        form = view.get_form()
        # Widget hasn't been replaced.
        from django.forms import HiddenInput

        self.assertNotIsInstance(form.fields["campaign"].widget, HiddenInput)

    def test_opt_out_disables_lockdown(self):
        active = _make_campaign("Activa3")
        request = self.factory.get("/")
        request.active_campaign = active
        view = _FakeCreateView(FieldSurvey, request, respect=False)
        form = view.get_form()
        from django.forms import HiddenInput

        self.assertNotIsInstance(form.fields["campaign"].widget, HiddenInput)

    def test_terminal_campaign_leaves_field_visible(self):
        # When the active campaign is CLOSED/CANCELED, the form must show
        # the campaign field as a visible select so the user picks an
        # operational campaign explicitly. Auto-fill would silently associate
        # the new record with a terminal campaign.
        from django.forms import HiddenInput

        closed = _make_campaign("Cerrada")
        _make_campaign("Operativa")
        # Bypass FSM rules — we only need the persisted state for the mixin's check.
        # ``refresh_from_db`` is blocked by django-fsm on the state field, so
        # re-fetch through ``objects.get`` instead.
        Campaign.objects.filter(pk=closed.pk).update(state=Campaign.workflow.CLOSED)
        closed = Campaign.objects.get(pk=closed.pk)
        request = self.factory.get("/")
        request.active_campaign = closed
        view = _FakeCreateView(FieldSurvey, request)
        form = view.get_form()
        field = form.fields["campaign"]
        self.assertNotIsInstance(field.widget, HiddenInput)
        # Queryset must NOT be narrowed to the closed campaign.
        self.assertGreater(field.queryset.count(), 1)

    def test_archived_campaign_leaves_field_visible(self):
        # Archived campaigns are browsing-only: the form must not auto-fill
        # them even when the workflow state is not terminal.
        from django.forms import HiddenInput

        archived = _make_campaign("ArchivadaForm", is_active=False)
        _make_campaign("OperativaForm")
        request = self.factory.get("/")
        request.active_campaign = archived
        view = _FakeCreateView(FieldSurvey, request)
        form = view.get_form()
        self.assertNotIsInstance(form.fields["campaign"].widget, HiddenInput)
        self.assertNotIn("campaign", view.get_initial())

    def test_initial_skips_terminal_campaign(self):
        # ``get_initial`` must not seed a closed campaign either — same
        # rationale as the form widget check above.
        canceled = _make_campaign("Anulada")
        Campaign.objects.filter(pk=canceled.pk).update(state=Campaign.workflow.CANCELED)
        canceled = Campaign.objects.get(pk=canceled.pk)
        request = self.factory.get("/")
        request.active_campaign = canceled
        view = _FakeCreateView(FieldSurvey, request)
        self.assertNotIn("campaign", view.get_initial())


def test_module_exports_present():
    """Sanity import — catches accidental name removals."""
    for name in ("ActiveCampaignMiddleware", "resolve_active_campaign", "SESSION_KEY"):
        assert hasattr(active_module, name)
