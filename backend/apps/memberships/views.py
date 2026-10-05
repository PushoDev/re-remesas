from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MembershipPlan
from .serializers import MembershipPlanSerializer, SubscribeResultSerializer, SubscribeSerializer
from .services import subscribe


class PlanListView(generics.ListAPIView):
    """GET /api/memberships/plans/ — the plans on sale, with benefits and price."""

    serializer_class = MembershipPlanSerializer
    permission_classes = [AllowAny]
    pagination_class = None
    queryset = MembershipPlan.objects.filter(is_active=True)


class SubscribeView(APIView):
    """POST /api/memberships/subscribe/ {plan_code, payment_method}

    Creates a pending purchase and tells the client where to pay. It never
    activates the membership: only a confirmed payment does.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription, _session = subscribe(
            request.user, serializer.validated_data['plan_code'], serializer.validated_data['payment_method'],
        )
        data = SubscribeResultSerializer({'subscription': subscription, 'payment': subscription.payment}).data
        return Response(data, status=status.HTTP_201_CREATED)
