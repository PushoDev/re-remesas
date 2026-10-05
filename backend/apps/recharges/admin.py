from django.contrib import admin

from .models import Promotion, RechargeOrder, RechargePackage


@admin.register(RechargePackage)
class RechargePackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'price', 'currency', 'is_active', 'is_demo', 'sort_order')
    list_filter = ('kind', 'is_active', 'is_demo')
    search_fields = ('code', 'name')


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ('title', 'package', 'starts_at', 'ends_at', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'title')


@admin.register(RechargeOrder)
class RechargeOrderAdmin(admin.ModelAdmin):
    list_display = ('reference', 'user', 'phone_number', 'package', 'amount_total', 'currency', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('reference', 'phone_number', 'user__email', 'provider_reference')
    # Orders are records of what happened: they are read here, never edited by hand.
    readonly_fields = [field.name for field in RechargeOrder._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
