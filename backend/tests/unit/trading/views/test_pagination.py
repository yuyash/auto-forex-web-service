"""Unit tests for trading views pagination."""

from apps.trading.views.pagination import StandardPagination, TaskSubResourcePagination


class TestStandardPagination:
    """Test StandardPagination class."""

    def test_page_size(self):
        assert StandardPagination.page_size == 50

    def test_max_page_size(self):
        assert StandardPagination.max_page_size == 200

    def test_page_size_query_param(self):
        assert StandardPagination.page_size_query_param == "page_size"


class TestTaskSubResourcePagination:
    """Test TaskSubResourcePagination class."""

    def test_page_size(self):
        assert TaskSubResourcePagination.page_size == 100

    def test_max_page_size(self):
        assert TaskSubResourcePagination.max_page_size == 1000

    def test_page_size_query_param(self):
        assert TaskSubResourcePagination.page_size_query_param == "page_size"
