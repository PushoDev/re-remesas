from django.urls import path

from . import views

urlpatterns = [
    path('memberships/plans/', views.PlanListView.as_view(), name='membership-plans'),
    path('memberships/subscribe/', views.SubscribeView.as_view(), name='membership-subscribe'),
]
