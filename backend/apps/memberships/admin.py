from django.contrib import admin

from .models import MembershipPlan, Subscription


@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'period', 'price', 'currency', 'duration_days', 'recharge_discount_percent',
                    'is_active', 'sort_order')
    list_filter = ('period', 'is_active')
    search_fields = ('name', 'code')
    list_editable = ('is_active', 'sort_order')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """Purchases are read-only: they change only through payments."""

    list_display = ('user', 'plan', 'status', 'starts_at', 'expires_at', 'created_at')
    list_filter = ('status', 'plan')
    search_fields = ('user__email',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
