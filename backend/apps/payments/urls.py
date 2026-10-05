from django.urls import path

from . import views

urlpatterns = [
    path('payments/webhooks/<str:provider>/', views.PaymentWebhookView.as_view(), name='payment-webhook'),
    path('payments/mock/<uuid:reference>/confirm/', views.MockCheckoutConfirmView.as_view(), name='payment-mock-confirm'),
    path('payments/<uuid:reference>/', views.PaymentDetailView.as_view(), name='payment-detail'),
]
