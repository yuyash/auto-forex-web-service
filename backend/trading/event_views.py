"""
API views for event logging and querying.

This module provides endpoints for:
- Querying events with filters
- Retrieving event details
- Exporting events to CSV

Requirements: 27.1, 27.2, 27.3, 27.4
"""

import csv
from datetime import datetime

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpResponse

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminUser
from trading.event_models import Event
from trading.serializers import EventSerializer

User = get_user_model()


class EventPagination(PageNumberPagination):
    """
    Pagination for event list.

    Requirements: 27.4
    """

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100


class EventListView(APIView):
    """
    API endpoint for querying events.

    GET /api/events
    - List events with filtering and search
    - Support pagination (50 events per page)
    - Filter by category, severity, date range, username
    - Full-text search on description

    Requirements: 27.1, 27.2, 27.3, 27.4
    """

    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = EventPagination

    def get(self, request: Request) -> Response:
        """
        Query events with filters.

        Query Parameters:
            category: Event category (trading, system, security, admin)
            severity: Event severity (debug, info, warning, error, critical)
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            username: Username to filter by
            search: Full-text search on description
            page: Page number
            page_size: Number of results per page (max 100)

        Returns:
            Paginated list of events
        """
        queryset = Event.objects.all()

        # Filter by category
        category = request.query_params.get("category")
        if category:
            queryset = queryset.filter(category=category)

        # Filter by severity
        severity = request.query_params.get("severity")
        if severity:
            queryset = queryset.filter(severity=severity)

        # Filter by date range
        start_date = request.query_params.get("start_date")
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                queryset = queryset.filter(timestamp__gte=start_dt)
            except ValueError:
                return Response(
                    {"error": "Invalid start_date format. Use ISO format."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        end_date = request.query_params.get("end_date")
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                queryset = queryset.filter(timestamp__lte=end_dt)
            except ValueError:
                return Response(
                    {"error": "Invalid end_date format. Use ISO format."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Filter by username
        username = request.query_params.get("username")
        if username:
            queryset = queryset.filter(user__username__iexact=username)

        # Full-text search on description
        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(description__icontains=search) | Q(details__icontains=search)
            )

        # Order by timestamp (newest first)
        queryset = queryset.order_by("-timestamp")

        # Paginate results
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)

        if page is not None:
            serializer = EventSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = EventSerializer(queryset, many=True)
        return Response(serializer.data)


class EventDetailView(APIView):
    """
    API endpoint for retrieving event details.

    GET /api/events/{id}
    - Get detailed information about a specific event

    Requirements: 27.1
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request: Request, event_id: int) -> Response:  # pylint: disable=unused-argument
        """
        Get event details.

        Args:
            request: HTTP request
            event_id: Event ID

        Returns:
            Event details
        """
        try:
            event = Event.objects.get(id=event_id)
        except Event.DoesNotExist:
            return Response(
                {"error": "Event not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = EventSerializer(event)
        return Response(serializer.data)


class EventExportView(APIView):
    """
    API endpoint for exporting events to CSV.

    GET /api/events/export
    - Export events to CSV format
    - Support same filters as event list

    Requirements: 27.1, 27.2, 27.3
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request: Request) -> HttpResponse:
        """
        Export events to CSV.

        Query Parameters:
            Same as EventListView

        Returns:
            CSV file download
        """
        queryset = Event.objects.all()

        # Apply same filters as EventListView
        category = request.query_params.get("category")
        if category:
            queryset = queryset.filter(category=category)

        severity = request.query_params.get("severity")
        if severity:
            queryset = queryset.filter(severity=severity)

        start_date = request.query_params.get("start_date")
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                queryset = queryset.filter(timestamp__gte=start_dt)
            except ValueError:
                pass

        end_date = request.query_params.get("end_date")
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                queryset = queryset.filter(timestamp__lte=end_dt)
            except ValueError:
                pass

        username = request.query_params.get("username")
        if username:
            queryset = queryset.filter(user__username__iexact=username)

        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(description__icontains=search) | Q(details__icontains=search)
            )

        # Order by timestamp
        queryset = queryset.order_by("-timestamp")

        # Create CSV response
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="events.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "Timestamp",
                "Category",
                "Event Type",
                "Severity",
                "Username",
                "Account ID",
                "Description",
                "IP Address",
                "Details",
            ]
        )

        for event in queryset:
            writer.writerow(
                [
                    event.timestamp.isoformat(),
                    event.category,
                    event.event_type,
                    event.severity,
                    event.user.username if event.user else "",
                    event.account.account_id if event.account else "",
                    event.description,
                    event.ip_address or "",
                    str(event.details),
                ]
            )

        return response
