"""Views for strategy configuration management."""

from uuid import UUID

from django.db import models
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trading.models import StrategyConfiguration
from apps.trading.serializers import (
    StrategyConfigCreateSerializer,
    StrategyConfigDetailSerializer,
    StrategyConfigListSerializer,
)
from apps.trading.views.pagination import TaskExecutionPagination


class StrategyConfigView(APIView):
    """List and create strategy configurations."""

    permission_classes = [IsAuthenticated]
    pagination_class = TaskExecutionPagination
    serializer_class = StrategyConfigListSerializer

    @extend_schema(
        summary="List strategy configurations",
        description="List all strategy configurations for the authenticated user",
        responses={200: StrategyConfigListSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        from apps.trading.models import StrategyConfiguration

        strategy_type = request.query_params.get("strategy_type")
        search = request.query_params.get("search")

        queryset = StrategyConfiguration.objects.filter(user=request.user.pk)
        if strategy_type:
            queryset = queryset.filter(strategy_type=strategy_type)
        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search) | models.Q(description__icontains=search)
            )

        queryset = queryset.order_by("-created_at")
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = StrategyConfigListSerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        summary="Create strategy configuration",
        description="Create a new strategy configuration",
        request=StrategyConfigCreateSerializer,
        responses={201: StrategyConfigDetailSerializer, 400: dict},
    )
    def post(self, request: Request) -> Response:
        serializer = StrategyConfigCreateSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            try:
                config = serializer.save()
                response_serializer = StrategyConfigDetailSerializer(config)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            except Exception as e:
                error_message = str(e)
                if "unique_user_config_name" in error_message or "duplicate key" in error_message:
                    return Response(
                        {"name": ["A configuration with this name already exists"]},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                raise

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StrategyConfigDetailView(APIView):
    """Retrieve, update, and delete a strategy configuration."""

    permission_classes = [IsAuthenticated]
    serializer_class = StrategyConfigDetailSerializer

    _config_id_param = OpenApiParameter(
        name="config_id",
        type={"type": "string", "format": "uuid"},
        location=OpenApiParameter.PATH,
        required=True,
        description="Strategy configuration UUID",
    )

    @extend_schema(
        summary="Get strategy configuration",
        description="Retrieve a specific strategy configuration",
        parameters=[_config_id_param],
        responses={200: StrategyConfigDetailSerializer, 404: dict},
    )
    def get(self, request: Request, config_id: UUID) -> Response:
        from apps.trading.serializers import StrategyConfigDetailSerializer

        try:
            config = StrategyConfiguration.objects.get(id=config_id, user=request.user.pk)
        except StrategyConfiguration.DoesNotExist:
            return Response({"error": "Configuration not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = StrategyConfigDetailSerializer(config)
        return Response(serializer.data)

    @extend_schema(
        summary="Update strategy configuration",
        description="Update an existing strategy configuration",
        parameters=[_config_id_param],
        request=StrategyConfigCreateSerializer,
        responses={200: StrategyConfigDetailSerializer, 400: dict, 404: dict},
    )
    def put(self, request: Request, config_id: UUID) -> Response:
        from apps.trading.serializers import (
            StrategyConfigCreateSerializer,
            StrategyConfigDetailSerializer,
        )

        try:
            config = StrategyConfiguration.objects.get(id=config_id, user=request.user.pk)
        except StrategyConfiguration.DoesNotExist:
            return Response({"error": "Configuration not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = StrategyConfigCreateSerializer(
            config, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            updated_config = serializer.save()
            response_serializer = StrategyConfigDetailSerializer(updated_config)
            return Response(response_serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Delete strategy configuration",
        description="Delete a strategy configuration (fails if in use by active tasks)",
        parameters=[_config_id_param],
        responses={204: None, 400: dict, 404: dict},
    )
    def delete(self, request: Request, config_id: UUID) -> Response:
        try:
            config = StrategyConfiguration.objects.get(id=config_id, user=request.user.pk)
        except StrategyConfiguration.DoesNotExist:
            return Response({"error": "Configuration not found"}, status=status.HTTP_404_NOT_FOUND)

        if config.is_in_use():
            return Response(
                {
                    "error": "Cannot delete configuration that is in use by active tasks",
                    "detail": "Stop or delete all tasks using this configuration first",
                },
                status=status.HTTP_409_CONFLICT,
            )

        config.delete()
        return Response(
            {"message": "Configuration deleted successfully"}, status=status.HTTP_204_NO_CONTENT
        )
