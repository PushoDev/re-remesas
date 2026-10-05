from django.urls import path

from . import views

urlpatterns = [
    path('recharges/packages/', views.PackageListView.as_view(), name='recharge-packages'),
    path('recharges/recent-contacts/', views.RecentContactsView.as_view(), name='recharge-recent-contacts'),
    path('recharges/quote/', views.QuoteView.as_view(), name='recharge-quote'),
    path('recharges/', views.RechargeListCreateView.as_view(), name='recharge-list-create'),
    path('recharges/<uuid:reference>/', views.RechargeDetailView.as_view(), name='recharge-detail'),
    path('admin/recharges/', views.AdminRechargeListView.as_view(), name='admin-recharge-list'),
]
