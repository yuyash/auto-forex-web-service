"""Unit tests for focused OANDA client collaborators."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from apps.market.services.oanda_clients import OandaAccountClient, OandaContextFactory


class TestOandaContextFactory:
    """Tests for OANDA v20 context construction helpers."""

    def test_stream_hostname_converts_rest_hostnames(self):
        factory = OandaContextFactory()

        assert factory.stream_hostname("api-fxpractice.oanda.com") == (
            "stream-fxpractice.oanda.com"
        )
        assert factory.stream_hostname("stream-fxpractice.oanda.com") == (
            "stream-fxpractice.oanda.com"
        )
        assert factory.stream_hostname("") == ""


class TestOandaAccountClient:
    """Tests for account-resource caching and parsing."""

    def test_get_resource_fetches_then_reuses_cached_value(self):
        response = SimpleNamespace(
            status=200,
            body={"account": SimpleNamespace(id="101-001")},
        )
        service = SimpleNamespace(
            api=SimpleNamespace(account=SimpleNamespace(get=MagicMock(return_value=response))),
            account=SimpleNamespace(account_id="101-001"),
            _account_resource_cache=None,
            _account_object_to_dict=MagicMock(return_value={"id": "101-001"}),
        )
        client = OandaAccountClient(service)

        first = client.get_resource()
        second = client.get_resource()

        assert first == {"id": "101-001"}
        assert second == {"id": "101-001"}
        service.api.account.get.assert_called_once_with("101-001")
