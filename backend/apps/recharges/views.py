from django.db.models import Max, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers, status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.remittances.pagination import RemittancePagination

from .models import RechargeOrder
from .serializers import (
    AdminRechargeOrderSerializer,
    CatalogEntrySerializer,
    CreateRechargeResultSerializer,
    CreateRechargeSerializer,
    QuoteRequestSerializer,
    QuoteResultSerializer,
    RechargeOrderDetailSerializer,
    RechargeOrderSerializer,
    RecentContactSerializer,
)
from .services import PackageNotAvailable, create_recharge_order, get_catalog, quote_recharge

RECENT_CONTACTS_LIMIT = 8


def filter_by_status(queryset, params):
    wanted = params.get('status')
    if wanted:
        if wanted not in RechargeOrder.Status.values:
            raise serializers.ValidationError({'status': ['Estado no válido.']})
        queryset = queryset.filter(status=wanted)
    return queryset


class PackageListView(APIView):
    """GET /api/recharges/packages/ — the catalog, each package with the promotion the server says is
    current (`active_promotion`, or null)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        response = Response(CatalogEntrySerializer(get_catalog(), many=True).data)
        response['Cache-Control'] = 'no-store'  # promotions come and go by the clock
        return response


class RecentContactsView(APIView):
    """GET /api/recharges/recent-contacts/ — numbers the caller topped up before, newest first. Derived from
    their own orders: there is no separate contacts table."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = (
            RechargeOrder.objects.filter(user=request.user).values('phone_number')
            .annotate(last_used_at=Max('created_at')).order_by('-last_used_at')[:RECENT_CONTACTS_LIMIT]
        )
        return Response(RecentContactSerializer(rows, many=True).data)


class QuoteView(APIView):
    """POST /api/recharges/quote/ {phone_number, package_code} -> price breakdown. Stores nothing: creating the
    order recomputes it on the server."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = QuoteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            quote = quote_recharge(request.user, data['package'], data['phone_number'])
        except PackageNotAvailable as exc:
            raise serializers.ValidationError({'package_code': [str(exc)]}) from None
        response = Response(QuoteResultSerializer(quote).data)
        response['Cache-Control'] = 'no-store'
        return response


class RechargeListCreateView(generics.ListAPIView):
    """/api/recharges/

    GET  -> the caller's own orders, newest first, paginated. Filter: ?status=PENDING_PAYMENT|PROCESSING|SUCCESS|FAILED.
    POST -> create an order {phone_number, package_code, payment_method} and its pending payment. The price is
            computed on the server; the provider is only asked once the payment is confirmed.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = RechargeOrderSerializer
    pagination_class = RemittancePagination

    def get_queryset(self):
        queryset = RechargeOrder.objects.filter(user=self.request.user).select_related('package')
        return filter_by_status(queryset, self.request.query_params)

    def post(self, request):
        serializer = CreateRechargeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            order, _session = create_recharge_order(
                request.user, package=data['package'], phone_number=data['phone_number'],
                payment_method=data['payment_method'],
            )
        except PackageNotAvailable as exc:
            raise serializers.ValidationError({'package_code': [str(exc)]}) from None
        result = CreateRechargeResultSerializer({'order': order, 'payment': order.payment}).data
        return Response(result, status=status.HTTP_201_CREATED)


class RechargeDetailView(generics.RetrieveAPIView):
    """GET /api/recharges/<reference>/ — only the owner. Someone else's order, or one that does not exist, is a
    404: its existence is not revealed."""

    permission_classes = [IsAuthenticated]
    serializer_class = RechargeOrderDetailSerializer

    def get_object(self):
        queryset = RechargeOrder.objects.filter(user=self.request.user).select_related('package', 'payment')
        return get_object_or_404(queryset, reference=self.kwargs['reference'])


class AdminRechargeListView(generics.ListAPIView):
    """GET /api/admin/recharges/ — every order, for administrators only.

    Filters: ?status=, ?search= (phone, customer email, order or provider reference).
    `needs_refund` marks orders whose payment was taken but whose top-up failed.
    """

    permission_classes = [IsAdminUser]
    serializer_class = AdminRechargeOrderSerializer
    pagination_class = RemittancePagination

    def get_queryset(self):
        queryset = RechargeOrder.objects.select_related('user', 'package', 'payment')
        queryset = filter_by_status(queryset, self.request.query_params)
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(phone_number__icontains=search) | Q(user__email__icontains=search)
                | Q(provider_reference__icontains=search) | Q(reference__icontains=search.lower()),
            )
        return queryset
