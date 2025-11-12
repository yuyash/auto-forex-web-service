"""
Views for manual OANDA synchronization.

This module provides endpoints to manually trigger synchronization
of orders and positions from OANDA API.

Requirements: 8.3, 9.1
"""

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import OandaAccount
from trading.oanda_sync_task import sync_account_task

logger = logging.getLogger(__name__)


class AccountSyncView(APIView):
    """
    API endpoint for manual account synchronization.

    POST /api/accounts/{account_id}/sync
    - Manually trigger synchronization for a specific account
    - Fetches latest orders and positions from OANDA
    - Reconciles with local database
    - Returns sync results

    Requirements: 8.3, 9.1
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, account_id: int) -> Response:
        """
        Trigger manual synchronization for an account.

        Args:
            request: HTTP request
            account_id: OANDA account ID

        Returns:
            Response with sync results
        """
        # Verify account belongs to user
        try:
            account = OandaAccount.objects.get(id=account_id, user=request.user.id)
        except OandaAccount.DoesNotExist:
            return Response(
                {"error": "Account not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if account is active
        if not account.is_active:
            return Response(
                {"error": "Account is not active"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(
            "Manual sync triggered for account %s by user %s",
            account.account_id,
            request.user.username,
        )

        try:
            # Trigger immediate sync task for this account
            task_result = sync_account_task.apply_async(
                args=[account.id],
                expires=240,  # Task expires after 4 minutes
            )

            # Wait for result with timeout
            results = task_result.get(timeout=240)

            # Return results
            if results["success"]:
                return Response(
                    {
                        "success": True,
                        "message": "Account synced successfully",
                        "account_id": account.account_id,
                        "order_discrepancies": results["order_discrepancies"],
                        "position_discrepancies": results["position_discrepancies"],
                        "total_updates": results["total_updates"],
                    },
                    status=status.HTTP_200_OK,
                )

            return Response(
                {
                    "success": False,
                    "message": "Sync completed with errors",
                    "errors": results["errors"],
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            error_msg = f"Sync task failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return Response(
                {"success": False, "message": error_msg},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
