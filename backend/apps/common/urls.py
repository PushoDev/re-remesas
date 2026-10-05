from django.urls import path

from . import views

urlpatterns = [
    path('admin/overview/', views.AdminOverviewView.as_view(), name='admin-overview'),
]
