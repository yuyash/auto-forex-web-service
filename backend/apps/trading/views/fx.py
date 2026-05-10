"""FX conversion views."""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trading.serializers.fx import FxRateQuerySerializer, FxRateResponseSerializer
from apps.trading.services.fx_rates import FX_CONVERSION


class FxRateView(APIView):
    """Resolve direct FX conversion rates for account/display currency values."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="trading_fx_rate",
        tags=["Trading"],
        parameters=[FxRateQuerySerializer],
        responses={200: FxRateResponseSerializer},
        description=(
            "Resolve a conversion multiplier between two currencies. Direct same-currency "
            "rates do not require market data; base/quote conversions use the supplied "
            "instrument mid price first, then fall back to stored tick data and common "
            "two-leg cross rates."
        ),
    )
    def get(self, request: Request) -> Response:
        """Return a direct FX rate when it can be resolved locally."""
        serializer = FxRateQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        instrument = data.get("instrument", "")
        fx_rate = FX_CONVERSION.rate(
            source_currency=data["source_currency"],
            target_currency=data["target_currency"],
            instrument=instrument,
            mid_price=data.get("mid_price"),
            as_of=data.get("as_of"),
        )
        if fx_rate is None:
            return Response(
                {
                    "detail": (
                        "Unable to resolve FX rate from the supplied currency pair, "
                        "instrument, mid_price, or stored market data."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        response = FxRateResponseSerializer(
            {
                "source_currency": fx_rate.source_currency,
                "target_currency": fx_rate.target_currency,
                "rate": fx_rate.rate,
                "instrument": instrument,
                "as_of": fx_rate.as_of,
                "source": fx_rate.source,
            }
        )
        return Response(response.data, status=status.HTTP_200_OK)
