from rest_framework import serializers

from .models import Payment, PaymentStatus


class PaymentSerializer(serializers.ModelSerializer):
    """What the owner of a payment may see. External references and provider internals stay hidden."""

    checkout_url = serializers.SerializerMethodField()
    requires_manual_confirmation = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = (
            'reference', 'purpose', 'method', 'provider', 'status', 'amount', 'currency',
            'instructions', 'checkout_url', 'requires_manual_confirmation', 'created_at', 'confirmed_at',
        )
        read_only_fields = fields

    def get_checkout_url(self, obj) -> str | None:
        """Where to pay, while it is still pending (simulated gateway only)."""
        if obj.provider == 'MOCK' and obj.status == PaymentStatus.PENDING:
            return f'/pay/mock/{obj.reference}'
        return None

    def get_requires_manual_confirmation(self, obj) -> bool:
        return obj.provider == 'MANUAL'
