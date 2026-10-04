from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .overview import build_overview


class AdminOverviewView(APIView):
    """GET /api/admin/overview/ — counters for the dashboard. Staff only, never cached."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        response = Response(build_overview())
        response['Cache-Control'] = 'no-store'
        return response
