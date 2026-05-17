"""Initial-position import endpoints."""

from __future__ import annotations

import logging
from typing import Any

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trading.services.initial_position_imports import (
    InitialPositionImportError,
    InitialPositionImportService,
)
from apps.trading.views.errors import api_error

logger = logging.getLogger(__name__)


class InitialPositionImportSourceSerializer(serializers.Serializer):
    """Serializer for a selectable initial-position import source."""

    task_type = serializers.CharField()
    id = serializers.UUIDField()
    name = serializers.CharField()
    status = serializers.CharField()
    instrument = serializers.CharField()
    config_id = serializers.UUIDField()
    config_name = serializers.CharField()
    strategy_type = serializers.CharField()
    updated_at = serializers.CharField(allow_null=True)


class InitialPositionImportResultSerializer(serializers.Serializer):
    """Serializer for imported editable initial-position cycles."""

    cycles = serializers.ListField(child=serializers.JSONField())
    source = serializers.CharField()
    summary = serializers.DictField()


class InitialPositionImportFromTaskSerializer(serializers.Serializer):
    """Request serializer for importing from another task."""

    source_task_type = serializers.CharField(max_length=16)
    source_task_id = serializers.UUIDField()
    target_task_type = serializers.CharField(max_length=16)
    target_config_id = serializers.UUIDField(required=False)


class InitialPositionImportFromOandaSerializer(serializers.Serializer):
    """Request serializer for importing from OANDA open trades."""

    account_id = serializers.IntegerField(min_value=1)
    config_id = serializers.UUIDField()
    instrument = serializers.CharField(max_length=20)


@extend_schema(
    tags=["Trading"],
    responses={
        200: inline_serializer(
            "InitialPositionImportSourceList",
            fields={"results": InitialPositionImportSourceSerializer(many=True)},
        )
    },
)
class InitialPositionImportSourcesView(APIView):
    """Return tasks whose current state can seed initial positions."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        results = InitialPositionImportService().list_sources(user=request.user)
        return Response({"results": results})


@extend_schema(
    tags=["Trading"],
    request=InitialPositionImportFromTaskSerializer,
    responses={200: InitialPositionImportResultSerializer},
)
class InitialPositionImportFromTaskView(APIView):
    """Import editable initial-position cycles from another task."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = InitialPositionImportFromTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            result = InitialPositionImportService().import_from_task(
                user=request.user,
                source_task_type=str(data["source_task_type"]),
                source_task_id=str(data["source_task_id"]),
                target_task_type=str(data["target_task_type"]),
                target_config_id=(
                    str(data["target_config_id"]) if data.get("target_config_id") else None
                ),
            )
        except InitialPositionImportError as exc:
            return Response(
                api_error(exc.public_message, code=exc.code),
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception("Unexpected initial-position task import failure")
            return Response(
                api_error(
                    "Failed to import initial positions from task",
                    code="initial_position_task_import_failed",
                ),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(result)


@extend_schema(
    tags=["Trading"],
    request=InitialPositionImportFromOandaSerializer,
    responses={200: InitialPositionImportResultSerializer},
)
class InitialPositionImportFromOandaView(APIView):
    """Import editable initial-position cycles from OANDA open trades."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = InitialPositionImportFromOandaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            result = InitialPositionImportService().import_from_oanda(
                user=request.user,
                account_id=int(data["account_id"]),
                config_id=str(data["config_id"]),
                instrument=str(data["instrument"]),
            )
        except InitialPositionImportError as exc:
            return Response(
                api_error(exc.public_message, code=exc.code),
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception("Unexpected OANDA initial-position import failure")
            return Response(
                api_error(
                    "Failed to import initial positions from OANDA",
                    code="initial_position_oanda_import_failed",
                ),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(result)
