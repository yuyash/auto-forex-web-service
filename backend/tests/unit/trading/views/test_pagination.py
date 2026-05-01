"""Unit tests for trading views pagination."""

from apps.trading.views.pagination import (
    ActivityPagination,
    StandardPagination,
    TradePositionPagination,
)


class TestStandardPagination:
    """Test StandardPagination class."""

    def test_page_size(self):
        assert StandardPagination.page_size == 50

    def test_max_page_size(self):
        assert StandardPagination.max_page_size == 200

    def test_page_size_query_param(self):
        assert StandardPagination.page_size_query_param == "page_size"


class TestActivityPagination:
    def test_page_size(self):
        assert ActivityPagination.page_size == 100

    def test_max_page_size(self):
        assert ActivityPagination.max_page_size == 1000


class TestTradePositionPagination:
    def test_page_size(self):
        assert TradePositionPagination.page_size == 100

    def test_max_page_size(self):
        assert TradePositionPagination.max_page_size == 1000
