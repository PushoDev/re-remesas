from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.exchange_rates.services import RateNotAvailable

from .models import Remittance
from .pagination import RemittancePagination
from .serializers import (
    CreateRemittanceResultSerializer,
    CreateRemittanceSerializer,
    QuoteRequestSerializer,
    QuoteResultSerializer,
    RemittanceDetailSerializer,
    RemittanceSerializer,
    build_quote,
)
from .services import create_remittance, normalize_tracking_id


class QuoteView(APIView):
    """POST /api/remittances/quote/ {amount, currency} -> what the recipient would get.

    Open to anyone (the calculator works before signing in). If the caller is a
    current member, the preferential rate applies automatically. It stores
    nothing: creating a remittance recomputes everything on the server.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = QuoteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quote = build_quote(request.user, serializer.validated_data)
        response = Response(QuoteResultSerializer(quote).data)
        response['Cache-Control'] = 'no-store'
        return response


class RemittanceListCreateView(generics.ListAPIView):
    """/api/remittances/

    GET  -> the caller's own remittances, newest first, paginated.
            Filters: ?status=PENDING_PAYMENT|PAID|COMPLETED|CANCELLED and ?search=<part of the tracking id>.
    POST -> request a remittance (PENDING_PAYMENT, with its tracking id and where to pay).
            Everything monetary is computed on the server.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = RemittanceSerializer
    pagination_class = RemittancePagination

    def get_queryset(self):
        queryset = Remittance.objects.filter(sender=self.request.user)
        wanted = self.request.query_params.get('status')
        if wanted:
            if wanted not in Remittance.Status.values:
                raise serializers.ValidationError({'status': ['Estado no válido.']})
            queryset = queryset.filter(status=wanted)
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(tracking_id__icontains=normalize_tracking_id(search))
        return queryset

    def post(self, request):
        serializer = CreateRemittanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            remittance, _session = create_remittance(request.user, **serializer.validated_data)
        except RateNotAvailable:
            currency = serializer.validated_data['currency']
            return Response(
                {'currency': [f'No hay una tasa de cambio disponible para {currency} en este momento.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = CreateRemittanceResultSerializer({'remittance': remittance, 'payment': remittance.payment}).data
        return Response(data, status=status.HTTP_201_CREATED)


class RemittanceDetailView(generics.RetrieveAPIView):
    """GET /api/remittances/<tracking_id>/ — only the owner. Someone else's remittance, or
    one that does not exist, is a 404: its existence is not revealed."""

    permission_classes = [IsAuthenticated]
    serializer_class = RemittanceDetailSerializer

    def get_object(self):
        queryset = Remittance.objects.filter(sender=self.request.user).select_related("payment")
        return get_object_or_404(queryset, tracking_id=normalize_tracking_id(self.kwargs['tracking_id']))
