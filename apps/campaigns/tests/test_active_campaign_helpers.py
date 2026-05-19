from unittest.mock import patch

from django.db import DatabaseError
from django.test import RequestFactory, TestCase

from apps.campaigns.active import get_session_campaign_id, resolve_active_campaign


class ActiveCampaignLowLevelHelperTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_resolve_active_campaign_returns_none_without_tenant(self):
        request = self.factory.get("/")
        request.session = {}
        self.assertIsNone(resolve_active_campaign(request))

    def test_get_session_campaign_id_returns_none_without_session(self):
        request = self.factory.get("/")
        self.assertIsNone(get_session_campaign_id(request))

    def test_get_session_campaign_id_returns_none_on_invalid_value(self):
        request = self.factory.get("/")
        request.session = {"active_campaign_id": "abc"}
        self.assertIsNone(get_session_campaign_id(request))

    def test_resolve_active_campaign_swallow_database_error(self):
        request = self.factory.get("/")
        request.session = {}
        request.tenant = type("Tenant", (), {"schema_name": "tenant_x"})()
        with patch("apps.campaigns.active._campaign_model") as campaign_model:
            campaign_model.return_value.objects.filter.side_effect = DatabaseError("boom")
            self.assertIsNone(resolve_active_campaign(request))
