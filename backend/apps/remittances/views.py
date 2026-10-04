from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.exchange_rates.services import RateNotAvailable

from .models import Remittance
from .pagination import RemittancePagination
from .serializers import (
    PaymentProofSerializer,
    AdminRemittanceDetailSerializer,
    AdminRemittanceListSerializer,
    StatusChangeSerializer,
    CreateRemittanceResultSerializer,
    CreateRemittanceSerializer,
    QuoteRequestSerializer,
    QuoteResultSerializer,
    RemittanceDetailSerializer,
    RemittanceSerializer,
    build_quote,
)
from .services import (
    InvalidTransition,
    NotAManualPayment,
    NoteRequired,
    ProofNotAccepted,
    cancel_remittance,
    complete_remittance,
    confirm_manual_payment,
    create_remittance,
    normalize_tracking_id,
    submit_payment_proof,
)


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


class AdminRemittanceViewSet(viewsets.ReadOnlyModelViewSet):
    """/api/admin/remittances/ — the administrator's inbox (HU-REM-02). Staff only.

    Filters: ?status=, ?search= (tracking id, sender email, recipient name or phone),
    ?ordering= (created_at, amount_sent, amount_cup, status; "-" for descending).
    PATCH <tracking_id>/status/ {status, note} moves a remittance through its states.
    """

    permission_classes = [IsAdminUser]
    pagination_class = RemittancePagination
    lookup_field = 'tracking_id'
    lookup_value_regex = '[A-Za-z0-9-]+'
    ORDERINGS = {'created_at', 'amount_sent', 'amount_cup', 'status'}

    def get_serializer_class(self):
        return AdminRemittanceListSerializer if self.action == 'list' else AdminRemittanceDetailSerializer

    def get_queryset(self):
        queryset = Remittance.objects.select_related('sender__profile', 'payment', 'payment__confirmed_by')
        if self.action != 'list':
            return queryset.prefetch_related('status_log__changed_by')

        params = self.request.query_params
        wanted = params.get('status')
        if wanted:
            if wanted not in Remittance.Status.values:
                raise serializers.ValidationError({'status': ['Estado no válido.']})
            queryset = queryset.filter(status=wanted)

        search = params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(tracking_id__icontains=normalize_tracking_id(search))
                | Q(sender__email__icontains=search)
                | Q(recipient_name__icontains=search)
                | Q(recipient_phone__icontains=search),
            )

        ordering = params.get('ordering', '-created_at')
        if ordering.lstrip('-') not in self.ORDERINGS:
            raise serializers.ValidationError({'ordering': ['Orden no válido.']})
        return queryset.order_by(ordering, '-id')

    def get_object(self):
        return get_object_or_404(
            self.get_queryset(), tracking_id=normalize_tracking_id(self.kwargs['tracking_id']),
        )

    PROOF_TYPES = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.pdf': 'application/pdf'}

    @action(detail=True, methods=['get'], url_path='proof')
    def proof(self, request, tracking_id=None):
        """The proof file, only for administrators. Files have no public URL: this is the only way out."""
        remittance = self.get_object()
        if not remittance.payment_proof:
            raise Http404
        extension = '.' + remittance.payment_proof.name.rsplit('.', 1)[-1].lower()
        response = FileResponse(
            remittance.payment_proof.open('rb'),
            content_type=self.PROOF_TYPES.get(extension, 'application/octet-stream'),
        )
        response['Content-Disposition'] = f'inline; filename="comprobante-{remittance.tracking_id}{extension}"'
        response['X-Content-Type-Options'] = 'nosniff'
        response['Cache-Control'] = 'private, no-store'
        return response

    @action(detail=True, methods=['patch'], url_path='status')
    def change_status(self, request, tracking_id=None):
        remittance = self.get_object()
        serializer = StatusChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target, note = serializer.validated_data['status'], serializer.validated_data['note']

        try:
            if target == Remittance.Status.PAID:
                confirm_manual_payment(remittance, request.user)
            elif target == Remittance.Status.COMPLETED:
                complete_remittance(remittance, request.user, note)
            else:
                cancel_remittance(remittance, request.user, note)
        except (InvalidTransition, NotAManualPayment) as exc:
            return Response({'status': [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        except NoteRequired as exc:
            return Response({'note': [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)

        return Response(AdminRemittanceDetailSerializer(self.get_object()).data)


class PaymentProofView(APIView):
    """POST /api/remittances/<tracking_id>/payment-proof/ — multipart {reference?, file?}.

    The customer tells us how they paid a manual method (Zelle, Wise, cash). Only the
    owner can send it, only while it waits for payment, and only a JPG/PNG/PDF whose
    real content matches its type, up to the configured size.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, tracking_id):
        queryset = Remittance.objects.filter(sender=request.user).select_related('payment')
        remittance = get_object_or_404(queryset, tracking_id=normalize_tracking_id(tracking_id))

        serializer = PaymentProofSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = submit_payment_proof(
                remittance, reference=serializer.validated_data['reference'], file=serializer.validated_data.get('file'),
            )
        except ProofNotAccepted as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(RemittanceDetailSerializer(updated).data)
