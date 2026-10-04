from django.contrib import admin, messages

from .models import Payment, PaymentStatus
from .services import settle_payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Read-only view of payments. The only change an administrator can make is to
    confirm or reject a MANUAL payment (Zelle, Wise, cash) after checking the proof."""

    list_display = ('reference', 'user', 'purpose', 'method', 'provider', 'amount', 'currency', 'status', 'created_at')
    list_filter = ('status', 'purpose', 'method', 'provider')
    search_fields = ('reference', 'user__email', 'external_reference')
    actions = ['confirm_manual_payments', 'reject_manual_payments']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def _settle(self, request, queryset, succeeded: bool):
        pending_manual = queryset.filter(status=PaymentStatus.PENDING, provider='MANUAL')
        changed = sum(settle_payment(payment.pk, succeeded).changed for payment in pending_manual)
        skipped = queryset.count() - changed
        self.message_user(request, f'{changed} pago(s) {"confirmado(s)" if succeeded else "rechazado(s)"}.')
        if skipped:
            self.message_user(
                request,
                f'{skipped} omitido(s): solo se resuelven aquí los pagos manuales que siguen pendientes.',
                level=messages.WARNING,
            )

    @admin.action(description='Confirmar pagos manuales seleccionados (comprobante verificado)')
    def confirm_manual_payments(self, request, queryset):
        self._settle(request, queryset, succeeded=True)

    @admin.action(description='Rechazar pagos manuales seleccionados')
    def reject_manual_payments(self, request, queryset):
        self._settle(request, queryset, succeeded=False)
