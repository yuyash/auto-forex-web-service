"""Unit tests for TradingTaskViewSet."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from rest_framework import status as http_status
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.trading.enums import TaskStatus
from apps.trading.views.trading import TradingTaskViewSet

factory = APIRequestFactory()


def _make_task(pk=1, task_status=TaskStatus.CREATED, name="trade-1"):
    task = MagicMock()
    task.pk = pk
    task.id = pk
    task.status = task_status
    task.name = name
    task.celery_task_id = "celery-1"
    task.oanda_account = MagicMock()
    task.oanda_account_id = 10
    return task


def _build_viewset(action="start"):
    vs = TradingTaskViewSet()
    vs.action = action
    vs.kwargs = {"pk": 1}
    vs.format_kwarg = None
    vs.task_service = MagicMock()
    return vs


def _drf_post(data=None, query=""):
    django_req = factory.post(f"/{query}", data=data or {}, format="json")
    django_req.user = MagicMock(pk=1, id=1)
    drf_req = Request(django_req, parsers=[])
    drf_req._user = django_req.user
    drf_req._full_data = data or {}
    return drf_req


def _drf_get(query=""):
    django_req = factory.get(f"/{query}")
    django_req.user = MagicMock(pk=1, id=1)
    drf_req = Request(django_req)
    drf_req._user = django_req.user
    return drf_req


class TestGetSerializerClass:
    """Tests for get_serializer_class."""

    def test_returns_create_serializer_for_create(self):
        vs = _build_viewset(action="create")
        cls = vs.get_serializer_class()
        assert cls.__name__ == "TradingTaskCreateSerializer"

    def test_returns_create_serializer_for_update(self):
        vs = _build_viewset(action="update")
        cls = vs.get_serializer_class()
        assert cls.__name__ == "TradingTaskCreateSerializer"

    def test_returns_create_serializer_for_partial_update(self):
        vs = _build_viewset(action="partial_update")
        cls = vs.get_serializer_class()
        assert cls.__name__ == "TradingTaskCreateSerializer"

    def test_returns_default_serializer_for_list(self):
        vs = _build_viewset(action="list")
        cls = vs.get_serializer_class()
        assert cls.__name__ == "TradingTaskSerializer"

    def test_returns_default_serializer_for_retrieve(self):
        vs = _build_viewset(action="retrieve")
        cls = vs.get_serializer_class()
        assert cls.__name__ == "TradingTaskSerializer"


class TestGetQueryset:
    """Tests for get_queryset."""

    @patch("apps.trading.views.trading.TradingTask")
    def test_filters_by_user(self, MockModel):
        request = _drf_get()
        vs = _build_viewset(action="list")
        vs.request = request

        qs = MagicMock()
        MockModel.objects.filter.return_value = qs
        qs.select_related.return_value = qs
        qs.order_by.return_value = qs

        vs.get_queryset()
        MockModel.objects.filter.assert_called_once_with(user=1)

    @patch("apps.trading.views.trading.TradingTask")
    def test_filters_by_status(self, MockModel):
        request = _drf_get(query="?status=running")
        vs = _build_viewset(action="list")
        vs.request = request

        qs = MagicMock()
        MockModel.objects.filter.return_value = qs
        qs.select_related.return_value = qs
        qs.filter.return_value = qs
        qs.order_by.return_value = qs

        vs.get_queryset()
        qs.filter.assert_any_call(status="running")

    @patch("apps.trading.views.trading.TradingTask")
    def test_filters_by_config_id(self, MockModel):
        request = _drf_get(query="?config_id=5")
        vs = _build_viewset(action="list")
        vs.request = request

        qs = MagicMock()
        MockModel.objects.filter.return_value = qs
        qs.select_related.return_value = qs
        qs.filter.return_value = qs
        qs.order_by.return_value = qs

        vs.get_queryset()
        qs.filter.assert_any_call(config_id=5)

    @patch("apps.trading.views.trading.TradingTask")
    def test_filters_by_account_id(self, MockModel):
        request = _drf_get(query="?account_id=10")
        vs = _build_viewset(action="list")
        vs.request = request

        qs = MagicMock()
        MockModel.objects.filter.return_value = qs
        qs.select_related.return_value = qs
        qs.filter.return_value = qs
        qs.order_by.return_value = qs

        vs.get_queryset()
        qs.filter.assert_any_call(oanda_account_id=10)


class TestPerformCreate:
    """Tests for perform_create."""

    def test_sets_user_from_request(self):
        request = _drf_post()
        vs = _build_viewset(action="create")
        vs.request = request

        serializer = MagicMock()
        vs.perform_create(serializer)
        serializer.save.assert_called_once_with(user=request.user)


class TestStart:
    """Tests for start action."""

    @patch("apps.trading.views.trading.TradingTask")
    def test_start_success(self, MockModel):
        mock_qs = MagicMock()
        MockModel.objects.filter.return_value = mock_qs
        mock_qs.exclude.return_value = mock_qs
        mock_qs.first.return_value = None

        task = _make_task(task_status=TaskStatus.CREATED)
        vs = _build_viewset(action="start")
        vs.get_object = MagicMock(return_value=task)
        vs.get_serializer = MagicMock(return_value=MagicMock(data={"id": 1}))
        vs.task_service.start_task.return_value = task

        request = _drf_post()
        vs.request = request

        response = vs.start(request, pk=1)
        assert response.status_code == 200
        assert "results" in response.data

    def test_start_wrong_status_returns_400(self):
        task = _make_task(task_status=TaskStatus.RUNNING)
        vs = _build_viewset(action="start")
        vs.get_object = MagicMock(return_value=task)

        request = _drf_post()
        vs.request = request

        response = vs.start(request, pk=1)
        assert response.status_code == http_status.HTTP_400_BAD_REQUEST

    def test_start_stopped_task_suggests_restart(self):
        task = _make_task(task_status=TaskStatus.STOPPED)
        vs = _build_viewset(action="start")
        vs.get_object = MagicMock(return_value=task)

        request = _drf_post()
        vs.request = request

        response = vs.start(request, pk=1)
        assert response.status_code == http_status.HTTP_400_BAD_REQUEST
        assert "restart" in response.data["detail"]

    @patch("apps.trading.views.trading.TradingTask")
    def test_start_conflict_active_task(self, MockModel):
        task = _make_task(task_status=TaskStatus.CREATED)
        active = _make_task(pk=2, task_status=TaskStatus.RUNNING, name="active-task")

        mock_qs = MagicMock()
        MockModel.objects.filter.return_value = mock_qs
        mock_qs.exclude.return_value = mock_qs
        mock_qs.first.return_value = active

        vs = _build_viewset(action="start")
        vs.get_object = MagicMock(return_value=task)

        request = _drf_post()
        vs.request = request

        response = vs.start(request, pk=1)
        assert response.status_code == http_status.HTTP_409_CONFLICT

    @patch("apps.trading.views.trading.TradingTask")
    def test_start_exception_returns_500(self, MockModel):
        mock_qs = MagicMock()
        MockModel.objects.filter.return_value = mock_qs
        mock_qs.exclude.return_value = mock_qs
        mock_qs.first.return_value = None

        task = _make_task(task_status=TaskStatus.CREATED)
        vs = _build_viewset(action="start")
        vs.get_object = MagicMock(return_value=task)
        vs.task_service.start_task.side_effect = Exception("fail")

        request = _drf_post()
        vs.request = request

        response = vs.start(request, pk=1)
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR


class TestStop:
    """Tests for stop action."""

    def test_stop_success_graceful(self):
        task = _make_task(task_status=TaskStatus.RUNNING)
        vs = _build_viewset(action="stop")
        vs.get_object = MagicMock(return_value=task)
        vs.task_service.stop_task.return_value = True

        request = _drf_post(data={"mode": "graceful"})
        vs.request = request

        response = vs.stop(request, pk=1)
        assert response.status_code == http_status.HTTP_202_ACCEPTED
        assert response.data["mode"] == "graceful"

    def test_stop_success_immediate(self):
        task = _make_task(task_status=TaskStatus.RUNNING)
        vs = _build_viewset(action="stop")
        vs.get_object = MagicMock(return_value=task)
        vs.task_service.stop_task.return_value = True

        request = _drf_post(data={"mode": "immediate"})
        vs.request = request

        response = vs.stop(request, pk=1)
        assert response.status_code == http_status.HTTP_202_ACCEPTED

    def test_stop_default_mode_is_graceful(self):
        task = _make_task(task_status=TaskStatus.RUNNING)
        vs = _build_viewset(action="stop")
        vs.get_object = MagicMock(return_value=task)
        vs.task_service.stop_task.return_value = True

        request = _drf_post()
        vs.request = request

        response = vs.stop(request, pk=1)
        assert response.status_code == http_status.HTTP_202_ACCEPTED
        assert response.data["mode"] == "graceful"

    def test_stop_failure_returns_500(self):
        task = _make_task(task_status=TaskStatus.RUNNING)
        vs = _build_viewset(action="stop")
        vs.get_object = MagicMock(return_value=task)
        vs.task_service.stop_task.return_value = False

        request = _drf_post()
        vs.request = request

        response = vs.stop(request, pk=1)
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_stop_value_error_returns_400(self):
        task = _make_task(task_status=TaskStatus.RUNNING)
        vs = _build_viewset(action="stop")
        vs.get_object = MagicMock(return_value=task)
        vs.task_service.stop_task.side_effect = ValueError("not stoppable")

        request = _drf_post()
        vs.request = request

        response = vs.stop(request, pk=1)
        assert response.status_code == http_status.HTTP_400_BAD_REQUEST

    def test_stop_unexpected_error_returns_500(self):
        task = _make_task(task_status=TaskStatus.RUNNING)
        vs = _build_viewset(action="stop")
        vs.get_object = MagicMock(return_value=task)
        vs.task_service.stop_task.side_effect = Exception("boom")

        request = _drf_post()
        vs.request = request

        response = vs.stop(request, pk=1)
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR


class TestRestart:
    """Tests for restart action."""

    def test_restart_success(self):
        task = _make_task(task_status=TaskStatus.STOPPED)
        vs = _build_viewset(action="restart")
        vs.get_object = MagicMock(return_value=task)
        vs.get_serializer = MagicMock(return_value=MagicMock(data={"id": 1}))
        vs.task_service.restart_task.return_value = task

        request = _drf_post()
        vs.request = request

        response = vs.restart(request, pk=1)
        assert response.status_code == 200

    def test_restart_value_error_returns_400(self):
        task = _make_task(task_status=TaskStatus.RUNNING)
        vs = _build_viewset(action="restart")
        vs.get_object = MagicMock(return_value=task)
        vs.task_service.restart_task.side_effect = ValueError("bad state")

        request = _drf_post()
        vs.request = request

        response = vs.restart(request, pk=1)
        assert response.status_code == http_status.HTTP_400_BAD_REQUEST

    def test_restart_exception_returns_500(self):
        task = _make_task(task_status=TaskStatus.STOPPED)
        vs = _build_viewset(action="restart")
        vs.get_object = MagicMock(return_value=task)
        vs.task_service.restart_task.side_effect = Exception("fail")

        request = _drf_post()
        vs.request = request

        response = vs.restart(request, pk=1)
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR


class TestPause:
    """Tests for pause action."""

    def test_pause_success(self):
        task = _make_task(task_status=TaskStatus.RUNNING)
        vs = _build_viewset(action="pause")
        vs.get_object = MagicMock(return_value=task)
        vs.get_serializer = MagicMock(return_value=MagicMock(data={"id": 1}))
        vs.task_service.pause_task.return_value = True

        request = _drf_post()
        vs.request = request

        response = vs.pause(request, pk=1)
        assert response.status_code == 200

    def test_pause_not_running_returns_400(self):
        task = _make_task(task_status=TaskStatus.CREATED)
        vs = _build_viewset(action="pause")
        vs.get_object = MagicMock(return_value=task)

        request = _drf_post()
        vs.request = request

        response = vs.pause(request, pk=1)
        assert response.status_code == http_status.HTTP_400_BAD_REQUEST

    def test_pause_failure_returns_500(self):
        task = _make_task(task_status=TaskStatus.RUNNING)
        vs = _build_viewset(action="pause")
        vs.get_object = MagicMock(return_value=task)
        vs.task_service.pause_task.return_value = False

        request = _drf_post()
        vs.request = request

        response = vs.pause(request, pk=1)
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_pause_exception_returns_500(self):
        task = _make_task(task_status=TaskStatus.RUNNING)
        vs = _build_viewset(action="pause")
        vs.get_object = MagicMock(return_value=task)
        vs.task_service.pause_task.side_effect = Exception("fail")

        request = _drf_post()
        vs.request = request

        response = vs.pause(request, pk=1)
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR


class TestResume:
    """Tests for resume action."""

    def test_resume_success(self):
        task = _make_task(task_status=TaskStatus.STOPPED)
        vs = _build_viewset(action="resume")
        vs.get_object = MagicMock(return_value=task)
        vs.get_serializer = MagicMock(return_value=MagicMock(data={"id": 1}))
        vs.task_service.resume_task.return_value = task

        request = _drf_post()
        vs.request = request

        response = vs.resume(request, pk=1)
        assert response.status_code == 200

    def test_resume_value_error_returns_400(self):
        task = _make_task(task_status=TaskStatus.STOPPED)
        vs = _build_viewset(action="resume")
        vs.get_object = MagicMock(return_value=task)
        vs.task_service.resume_task.side_effect = ValueError("bad state")

        request = _drf_post()
        vs.request = request

        response = vs.resume(request, pk=1)
        assert response.status_code == http_status.HTTP_400_BAD_REQUEST

    def test_resume_exception_returns_500(self):
        task = _make_task(task_status=TaskStatus.STOPPED)
        vs = _build_viewset(action="resume")
        vs.get_object = MagicMock(return_value=task)
        vs.task_service.resume_task.side_effect = Exception("fail")

        request = _drf_post()
        vs.request = request

        response = vs.resume(request, pk=1)
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
