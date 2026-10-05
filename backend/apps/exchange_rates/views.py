from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ExchangeRate
from .serializers import ExchangeRateHistorySerializer, ExchangeRateSerializer, PublicExchangeRateSerializer
from .services import save_exchange_rate, user_gets_vip_rate


class AdminExchangeRateViewSet(viewsets.ModelViewSet):
    """/api/admin/exchange-rates/ — admin-only CRUD of rates and margins (HU-ADM-01).

    * Updates are PATCH only (partial); PUT is not exposed.
    * DELETE deactivates the rate instead of erasing it, so its history (who
      changed what, and when) is never lost. A deactivated rate can be
      replaced by a new active one.
    * Filters: `?currency=USD`, `?is_active=true|false`.
    """

    serializer_class = ExchangeRateSerializer
    permission_classes = [IsAdminUser]
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        queryset = ExchangeRate.objects.select_related('updated_by')
        currency = self.request.query_params.get('currency')
        if currency:
            queryset = queryset.filter(currency=currency.upper())
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() in ('1', 'true', 'yes'))
        return queryset

    def perform_destroy(self, instance):
        instance.is_active = False
        save_exchange_rate(instance, self.request.user)

    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        entries = self.get_object().history.select_related('changed_by')
        return Response(ExchangeRateHistorySerializer(entries, many=True).data, status=status.HTTP_200_OK)


class PublicExchangeRateList(APIView):
    """GET /api/exchange-rates/ — active rates as the asking viewer would get them.

    Anyone can read it; a logged-in member (active, unexpired VIP) sees the
    preferential rate. It is never cached, so an admin change shows up on the
    very next request.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        rates = ExchangeRate.objects.filter(is_active=True).order_by('currency')
        serializer = PublicExchangeRateSerializer(
            rates, many=True, context={'is_vip': user_gets_vip_rate(request.user)},
        )
        response = Response(serializer.data)
        response['Cache-Control'] = 'no-store'
        return response
