from django.urls import path

from . import views

urlpatterns = [
    path('remittances/quote/', views.QuoteView.as_view(), name='remittance-quote'),
    path('remittances/', views.RemittanceListCreateView.as_view(), name='remittance-list-create'),
    path('remittances/<str:tracking_id>/', views.RemittanceDetailView.as_view(), name='remittance-detail'),
]
