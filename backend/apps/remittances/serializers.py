import re
from decimal import Decimal

from rest_framework import serializers

from apps.common.phone import InvalidCubanPhone, normalize_cuban_mobile
from apps.exchange_rates.models import Currency
from apps.exchange_rates.services import RateNotAvailable
from apps.payments.models import PaymentMethod
from apps.payments.serializers import PaymentSerializer

from .models import Remittance
from .services import AmountOutOfRange, check_amount, quote_remittance


_PLAIN_NUMBER = re.compile(r'^-?\d+(\.\d+)?$')


class PlainDecimalField(serializers.DecimalField):
    """A decimal that, when sent as text, must be written plainly ("10.50"): no
    exponents ("1e3"), no signs other than "-", no hex. JSON numbers are fine."""

    def to_internal_value(self, data):
        if isinstance(data, str) and not _PLAIN_NUMBER.match(data.strip()):
            self.fail('invalid')
        return super().to_internal_value(data)


class QuoteRequestSerializer(serializers.Serializer):
    amount = PlainDecimalField(
        max_digits=12, decimal_places=2,
        error_messages={
            'required': 'Ingresa el monto.',
            'invalid': 'Ingresa un monto válido.',
            'null': 'Ingresa el monto.',
            'max_decimal_places': 'El monto admite máximo 2 decimales.',
            'max_digits': 'El monto es demasiado grande.',
            'max_whole_digits': 'El monto es demasiado grande.',
        },
    )
    currency = serializers.ChoiceField(
        choices=Currency.choices,
        error_messages={'required': 'Elige la moneda.', 'invalid_choice': 'Moneda no válida. Usa USD o EUR.'},
    )

    def validate_amount(self, value: Decimal) -> Decimal:
        try:
            check_amount(value)
        except AmountOutOfRange as exc:
            raise serializers.ValidationError(str(exc)) from None
        return value


class QuoteResultSerializer(serializers.Serializer):
    """What the calculator shows. Built from a RemittanceQuote; decimals go out as strings."""

    currency = serializers.CharField(source='rate.currency')
    target_currency = serializers.SerializerMethodField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, source='rate.amount')
    base_rate = serializers.DecimalField(max_digits=18, decimal_places=6, source='rate.base_rate')
    spread_percent = serializers.DecimalField(max_digits=5, decimal_places=2, source='rate.spread_percent')
    effective_rate = serializers.DecimalField(max_digits=18, decimal_places=4, source='rate.effective_rate')
    amount_cup = serializers.DecimalField(max_digits=14, decimal_places=2, source='rate.amount_cup')
    is_vip_rate = serializers.BooleanField(source='rate.is_vip_rate')
    standard_effective_rate = serializers.DecimalField(
        max_digits=18, decimal_places=4, allow_null=True, default=None)
    saving_cup = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True, default=None)

    def get_target_currency(self, obj) -> str:
        return 'CUP'


def build_quote(user, validated_data):
    """Quote for validated input, mapping a missing rate to a clear field error."""
    try:
        return quote_remittance(user, validated_data['amount'], validated_data['currency'])
    except RateNotAvailable:
        raise serializers.ValidationError(
            {'currency': [f'No hay una tasa de cambio disponible para {validated_data["currency"]} en este momento.']},
        ) from None


class CreateRemittanceSerializer(QuoteRequestSerializer):
    """The only things the client decides: how much, to whom, how it is delivered and
    how it is paid. Rates, CUP amounts, status and tracking id are never read from the request."""

    recipient_name = serializers.CharField(
        max_length=120,
        error_messages={'required': 'Ingresa el nombre del destinatario.', 'blank': 'Ingresa el nombre del destinatario.',
                        'max_length': 'El nombre es demasiado largo (máximo 120 caracteres).'},
    )
    recipient_phone = serializers.CharField(
        error_messages={'required': 'Ingresa el teléfono del destinatario.',
                        'blank': 'Ingresa el teléfono del destinatario.'},
    )
    delivery_method = serializers.ChoiceField(
        choices=Remittance.DeliveryMethod.choices,
        error_messages={'required': 'Elige cómo se entregará.', 'invalid_choice': 'Método de entrega no válido.'},
    )
    recipient_address = serializers.CharField(required=False, allow_blank=True, max_length=255, default='')
    recipient_account = serializers.CharField(required=False, allow_blank=True, max_length=60, default='')
    payment_method = serializers.ChoiceField(
        choices=PaymentMethod.choices,
        error_messages={'required': 'Elige un medio de pago.', 'invalid_choice': 'Medio de pago no válido.'},
    )

    def validate_recipient_name(self, value: str) -> str:
        value = ' '.join(value.split())
        if len(value) < 2:
            raise serializers.ValidationError('Ingresa el nombre completo del destinatario.')
        return value

    def validate_recipient_phone(self, value: str) -> str:
        try:
            return normalize_cuban_mobile(value)
        except InvalidCubanPhone as exc:
            raise serializers.ValidationError(str(exc)) from None

    def validate(self, attrs):
        method = attrs['delivery_method']
        address = ' '.join(attrs.get('recipient_address', '').split())
        account = re.sub(r'[\s-]', '', attrs.get('recipient_account', ''))

        if method == Remittance.DeliveryMethod.CASH_DELIVERY:
            if not address:
                raise serializers.ValidationError(
                    {'recipient_address': ['Ingresa la dirección donde se entregará el efectivo.']})
            account = ''  # not needed for this method: do not keep stray data
        else:
            if not account:
                raise serializers.ValidationError(
                    {'recipient_account': ['Ingresa la cuenta o tarjeta que recibirá la transferencia.']})
            if not re.fullmatch(r'\d{12,20}', account):
                raise serializers.ValidationError(
                    {'recipient_account': ['La cuenta debe tener entre 12 y 20 dígitos.']})
            address = ''

        attrs['recipient_address'], attrs['recipient_account'] = address, account
        return attrs


class RemittanceSerializer(serializers.ModelSerializer):
    """What the owner sees of a remittance. No internal ids, no sender data."""

    target_currency = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    delivery_method_display = serializers.CharField(source='get_delivery_method_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)

    class Meta:
        model = Remittance
        fields = (
            'tracking_id', 'status', 'status_display', 'amount_sent', 'currency', 'target_currency',
            'base_rate_used', 'spread_percent_used', 'effective_rate_used', 'amount_cup', 'is_vip_rate',
            'recipient_name', 'recipient_phone', 'recipient_address', 'recipient_account',
            'delivery_method', 'delivery_method_display', 'payment_method', 'payment_method_display',
            'created_at', 'updated_at',
        )
        read_only_fields = fields

    def get_target_currency(self, obj) -> str:
        return 'CUP'


class CreateRemittanceResultSerializer(serializers.Serializer):
    remittance = RemittanceSerializer()
    payment = PaymentSerializer()


class RemittanceDetailSerializer(RemittanceSerializer):
    """The remittance plus its payment, so the owner can resume paying or follow the state."""

    payment = PaymentSerializer(read_only=True)

    class Meta(RemittanceSerializer.Meta):
        fields = RemittanceSerializer.Meta.fields + ('payment',)
        read_only_fields = fields
