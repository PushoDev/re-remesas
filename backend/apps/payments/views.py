from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Payment
from .providers.base import InvalidWebhook, WebhookNotSupported
from .providers.mock import build_signed_event
from .serializers import PaymentSerializer
from .services import PaymentNotFound, UnknownProvider, handle_webhook


class PaymentDetailView(generics.RetrieveAPIView):
    """GET /api/payments/<reference>/ — the owner checks the state of their payment."""

    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'reference'

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)


class PaymentWebhookView(APIView):
    """POST /api/payments/webhooks/<provider>/ — called by the payment gateway.

    Public on purpose (the gateway has no session), so trust comes only from the
    provider's signature, which is verified before anything else happens.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, provider):
        try:
            result = handle_webhook(provider, request.body, request.headers)
        except InvalidWebhook:
            return Response({'detail': 'Webhook no válido.'}, status=status.HTTP_400_BAD_REQUEST)
        except (UnknownProvider, WebhookNotSupported, PaymentNotFound):
            return Response({'detail': 'No encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'status': 'ok', 'processed': result.changed})


class MockCheckoutConfirmView(APIView):
    """POST /api/payments/mock/<reference>/confirm/ {"outcome": "succeeded"|"failed"}

    The "pay" button of the simulated checkout. It does not touch the payment
    directly: it builds the same signed event a real gateway would send and runs
    it through the webhook handler. Exists only while PAYMENT_MOCK_ENABLED is on,
    and only for the owner of a payment handled by the simulated gateway.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, reference):
        if not settings.PAYMENT_MOCK_ENABLED:
            raise Http404
        payment = get_object_or_404(Payment, reference=reference, user=request.user, provider='MOCK')

        outcome = request.data.get('outcome')
        if outcome not in ('succeeded', 'failed'):
            return Response({'outcome': ['Debe ser "succeeded" o "failed".']}, status=status.HTTP_400_BAD_REQUEST)

        body, headers = build_signed_event(payment.external_reference, outcome == 'succeeded')
        result = handle_webhook('MOCK', body, headers)
        return Response(PaymentSerializer(result.payment).data)
