"""Server-sent task update streams."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from typing import Any
from uuid import UUID

from django.http import Http404, StreamingHttpResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BaseRenderer
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.trading.enums import TaskType
from apps.trading.models import BacktestTask, TradingTask

logger = logging.getLogger(__name__)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


class ServerSentEventRenderer(BaseRenderer):
    """Renderer used only for DRF content negotiation on SSE endpoints."""

    media_type = "text/event-stream"
    format = "event-stream"
    charset = "utf-8"

    def render(
        self,
        data: Any,
        accepted_media_type: str | None = None,
        renderer_context: dict[str, Any] | None = None,
    ) -> bytes:
        _ = accepted_media_type
        _ = renderer_context
        if data is None:
            return b""
        if isinstance(data, bytes):
            return data
        return str(data).encode(self.charset)


class TaskEventStreamView(APIView):
    """Stream lightweight task status snapshots over Server-Sent Events."""

    permission_classes = [IsAuthenticated]
    renderer_classes = [ServerSentEventRenderer]
    poll_interval_seconds = 3

    @extend_schema(exclude=True)
    def get(self, request: Request, task_type: str, task_id: UUID) -> StreamingHttpResponse:
        task_type = self._normalize_task_type(task_type)
        task_model = self._task_model(task_type)
        task = task_model.objects.filter(pk=task_id, user=request.user.pk).first()
        if task is None:
            raise Http404("Task not found")

        response = StreamingHttpResponse(
            self._event_stream(
                request,
                task_model=task_model,
                task_id=task_id,
            ),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    def _event_stream(
        self,
        request: Request,
        *,
        task_model: type[BacktestTask] | type[TradingTask],
        task_id: UUID,
    ) -> Iterator[str]:
        last_payload: dict[str, Any] | None = None

        try:
            while True:
                if getattr(request, "_streaming_aborted", False):
                    return

                task = task_model.objects.filter(pk=task_id, user=request.user.pk).first()
                if task is None:
                    return

                payload = self._snapshot(task)
                if payload != last_payload:
                    yield _sse("snapshot", payload)
                    last_payload = payload
                else:
                    yield _sse("heartbeat", {"timestamp": timezone.now().isoformat()})

                time.sleep(self.poll_interval_seconds)
        except Exception:
            logger.exception("Task event stream aborted")
            return

    @staticmethod
    def _snapshot(task: BacktestTask | TradingTask) -> dict[str, Any]:
        return {
            "status": task.status,
            "progress": getattr(task, "progress", None),
            "execution_id": str(task.execution_id) if task.execution_id else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "error_message": task.error_message,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        }

    @staticmethod
    def _task_model(task_type: str):
        if task_type == TaskType.BACKTEST:
            return BacktestTask
        if task_type == TaskType.TRADING:
            return TradingTask
        raise Http404("Task type not found")

    @staticmethod
    def _normalize_task_type(task_type: str) -> str:
        if task_type == "backtest":
            return "backtest"
        if task_type == "trading":
            return "trading"
        raise Http404("Task type not found")
