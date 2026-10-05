from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register('admin/exchange-rates', views.AdminExchangeRateViewSet, basename='admin-exchange-rate')

urlpatterns = [
    path('exchange-rates/', views.PublicExchangeRateList.as_view(), name='exchange-rates'),
    *router.urls,
]
