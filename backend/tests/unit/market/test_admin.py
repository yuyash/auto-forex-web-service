from __future__ import annotations


class TestMarketAdminModule:
    def test_import(self) -> None:
        import apps.market.admin as _admin

        assert _admin is not None
