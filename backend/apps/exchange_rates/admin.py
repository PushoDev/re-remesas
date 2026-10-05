from django.contrib import admin

from .models import ExchangeRate, ExchangeRateHistory
from .services import save_exchange_rate


class HistoryInline(admin.TabularInline):
    model = ExchangeRateHistory
    extra = 0
    can_delete = False
    readonly_fields = (
        'base_rate', 'standard_spread_percent', 'vip_spread_percent', 'is_active', 'changed_by', 'changed_at',
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = (
        'currency', 'target_currency', 'base_rate', 'standard_spread_percent',
        'vip_spread_percent', 'is_active', 'updated_at', 'updated_by',
    )
    list_filter = ('currency', 'is_active')
    readonly_fields = ('target_currency', 'created_at', 'updated_at', 'updated_by')
    inlines = [HistoryInline]

    def save_model(self, request, obj, form, change):
        save_exchange_rate(obj, request.user)  # records the history and the author
