"""Shared base classes for task viewsets."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from django.db.models import Q, QuerySet
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.trading.tasks.service import TaskService
from apps.trading.views.mixins import TaskSubResourceMixin


class TaskViewSetBase(TaskSubResourceMixin, ModelViewSet):
    """Common behavior for backtest and trading task viewsets."""

    permission_classes = [IsAuthenticated]
    detail_serializer_class = None
    list_serializer_class = None
    create_serializer_class = None
    task_model_name: str | None = None
    select_related_fields: tuple[str, ...] = ()
    filter_field_map: dict[str, str] = {}
    task_type_label: str

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.task_service: TaskService = TaskService()

    def get_serializer_class(self):
        if self.action == "list" and self.list_serializer_class is not None:
            return self.list_serializer_class
        if (
            self.action in {"create", "update", "partial_update"}
            and self.create_serializer_class is not None
        ):
            return self.create_serializer_class
        if self.detail_serializer_class is not None:
            return self.detail_serializer_class
        return super().get_serializer_class()

    def get_queryset(self) -> QuerySet:
        """Return tasks for the authenticated user with common filtering."""
        assert isinstance(self.request, Request)
        task_model = self._get_task_model()
        assert task_model is not None

        queryset = task_model.objects.filter(user=self.request.user.pk)
        if self.select_related_fields:
            queryset = queryset.select_related(*self.select_related_fields)

        for param_name, field_name in self.filter_field_map.items():
            raw_value = self.request.query_params.get(param_name)
            if not raw_value:
                continue
            queryset = queryset.filter(**{field_name: self._coerce_filter_value(raw_value)})

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(description__icontains=search))

        ordering = self.request.query_params.get("ordering", "-created_at")
        return queryset.order_by(ordering)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers({})
        return Response(
            self._serialize_detail(serializer.instance),
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(self._serialize_detail(serializer.instance))

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def _serialize_detail(self, instance: Any) -> dict[str, Any]:
        serializer = self.get_serializer(instance)
        return serializer.data

    @staticmethod
    def _coerce_filter_value(raw_value: str) -> Any:
        if raw_value.isdigit():
            return int(raw_value)
        return raw_value

    def _get_task_model(self):
        if self.task_model_name is None:
            return None
        module = import_module(self.__module__)
        return getattr(module, self.task_model_name)
