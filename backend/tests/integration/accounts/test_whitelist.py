"""Regression tests ensuring removed whitelist admin endpoints stay removed.

The whitelist admin API surface was intentionally deleted.
These tests assert the old routes return 404.
"""

import pytest
import requests


@pytest.mark.django_db(transaction=True)
class TestWhitelistEndpointsRemoved:
    def test_list_route_returns_404(self, live_server, admin_auth_headers):
        url = f"{live_server.url}/api/admin/whitelist/emails"

        assert requests.get(url, timeout=10).status_code == 404
        assert requests.get(url, headers=admin_auth_headers, timeout=10).status_code == 404

    def test_detail_route_returns_404(self, live_server, admin_auth_headers):
        url = f"{live_server.url}/api/admin/whitelist/emails/1"

        assert requests.get(url, timeout=10).status_code == 404
        assert requests.get(url, headers=admin_auth_headers, timeout=10).status_code == 404
