from rest_framework import serializers

from apps.common.phone import InvalidCubanPhone, normalize_cuban_mobile
from apps.payments.models import PaymentMethod, PaymentStatus
from apps.payments.serializers import PaymentSerializer

from .models import Promotion, RechargeOrder, RechargePackage


class PromotionSerializer(serializers.ModelSerializer):
    """The promotion the server says is current. The browser only draws it."""

    class Meta:
        model = Promotion
        fields = ('code', 'title', 'description', 'ends_at')
        read_only_fields = fields


class PackageSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)

    class Meta:
        model = RechargePackage
        fields = ('code', 'name', 'kind', 'kind_display', 'price', 'currency', 'description')
        read_only_fields = fields


class CatalogEntrySerializer(PackageSerializer):
    """A package of the catalog, with its current promotion (or null)."""

    active_promotion = serializers.SerializerMethodField()

    class Meta(PackageSerializer.Meta):
        fields = PackageSerializer.Meta.fields + ('active_promotion',)
        read_only_fields = fields

    def get_active_promotion(self, entry) -> dict | None:
        return PromotionSerializer(entry.active_promotion).data if entry.active_promotion else None

    def to_representation(self, entry):
        data = PackageSerializer(entry.package).data
        data['active_promotion'] = self.get_active_promotion(entry)
        return data


class QuoteRequestSerializer(serializers.Serializer):
    """Phone and package are all the client decides; the price is computed on the server."""

    phone_number = serializers.CharField(
        error_messages={'required': 'Ingresa el teléfono.', 'blank': 'Ingresa el teléfono.', 'null': 'Ingresa el teléfono.'},
    )
    package_code = serializers.CharField(
        error_messages={'required': 'Elige un paquete.', 'blank': 'Elige un paquete.', 'null': 'Elige un paquete.'},
    )

    def validate_phone_number(self, value: str) -> str:
        try:
            return normalize_cuban_mobile(value)
        except InvalidCubanPhone as exc:
            raise serializers.ValidationError(str(exc)) from None

    def validate_package_code(self, value: str) -> str:
        package = RechargePackage.objects.filter(code=value.strip()).first()
        if package is None:
            raise serializers.ValidationError('Paquete no válido.')
        if not package.is_active:
            raise serializers.ValidationError('Este paquete no está disponible.')
        self._package = package
        return package.code

    def validate(self, attrs):
        attrs['package'] = self._package
        return attrs


class CreateRechargeSerializer(QuoteRequestSerializer):
    payment_method = serializers.ChoiceField(
        choices=PaymentMethod.choices,
        error_messages={'required': 'Elige un medio de pago.', 'invalid_choice': 'Medio de pago no válido.'},
    )


class QuoteResultSerializer(serializers.Serializer):
    """The breakdown the customer sees. Decimals go out as strings."""

    package = PackageSerializer()
    phone_number = serializers.CharField()
    price_base = serializers.DecimalField(max_digits=10, decimal_places=2)
    discount_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    amount_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()
    is_vip = serializers.BooleanField()
    active_promotion = PromotionSerializer(allow_null=True)


class RechargeOrderSerializer(serializers.ModelSerializer):
    """An order as its owner sees it."""

    package = PackageSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    promotion = serializers.JSONField(source='promotion_snapshot', read_only=True)

    class Meta:
        model = RechargeOrder
        fields = (
            'reference', 'phone_number', 'package', 'price_base', 'discount_percent_applied', 'amount_total',
            'currency', 'promotion', 'status', 'status_display', 'provider_reference', 'provider_message',
            'created_at', 'updated_at',
        )
        read_only_fields = fields


class RechargeOrderDetailSerializer(RechargeOrderSerializer):
    """The order plus its payment, so the owner can resume paying."""

    payment = PaymentSerializer(read_only=True)

    class Meta(RechargeOrderSerializer.Meta):
        fields = RechargeOrderSerializer.Meta.fields + ('payment',)
        read_only_fields = fields


class CreateRechargeResultSerializer(serializers.Serializer):
    order = RechargeOrderSerializer()
    payment = PaymentSerializer()


class RecentContactSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    last_used_at = serializers.DateTimeField()


class AdminRechargeOrderSerializer(RechargeOrderSerializer):
    """One row of the administrator's list: who, what, how much, and what the provider answered."""

    user_email = serializers.EmailField(source='user.email', read_only=True)
    payment_method = serializers.CharField(source='payment.method', read_only=True)
    payment_status = serializers.CharField(source='payment.status', read_only=True)
    needs_refund = serializers.SerializerMethodField()

    class Meta(RechargeOrderSerializer.Meta):
        fields = RechargeOrderSerializer.Meta.fields + ('user_email', 'payment_method', 'payment_status', 'needs_refund')
        read_only_fields = fields

    def get_needs_refund(self, order) -> bool:
        """The money was taken but the top-up did not happen: someone must refund it by hand."""
        return order.status == RechargeOrder.Status.FAILED and order.payment.status == PaymentStatus.SUCCEEDED
