from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register('admin/remittances', views.AdminRemittanceViewSet, basename='admin-remittance')

urlpatterns = [
    path('remittances/quote/', views.QuoteView.as_view(), name='remittance-quote'),
    path('remittances/', views.RemittanceListCreateView.as_view(), name='remittance-list-create'),
    path('remittances/<str:tracking_id>/', views.RemittanceDetailView.as_view(), name='remittance-detail'),
    path('remittances/<str:tracking_id>/payment-proof/', views.PaymentProofView.as_view(), name='remittance-proof'),
    *router.urls,
]
