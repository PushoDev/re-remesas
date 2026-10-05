import re
from decimal import Decimal
from pathlib import PurePath

from django.conf import settings
from rest_framework import serializers

from apps.common.phone import InvalidCubanPhone, normalize_cuban_mobile
from apps.exchange_rates.models import Currency
from apps.exchange_rates.services import RateNotAvailable
from apps.payments.models import PaymentMethod
from apps.payments.serializers import PaymentSerializer

from .models import Remittance, RemittanceStatusLog
from .services import AmountOutOfRange, allowed_actions, check_amount, quote_remittance


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
    payment_reference = serializers.CharField(read_only=True)
    has_proof_file = serializers.SerializerMethodField()
    status_log = serializers.SerializerMethodField()

    class Meta(RemittanceSerializer.Meta):
        fields = RemittanceSerializer.Meta.fields + ('payment', 'payment_reference', 'has_proof_file', 'status_log')
        read_only_fields = fields

    def get_has_proof_file(self, obj) -> bool:
        return bool(obj.payment_proof)

    def get_status_log(self, obj) -> list[dict]:
        """The timeline the customer sees: states and when. Internal notes and who acted stay private."""
        return [
            {'from_status': e.from_status, 'to_status': e.to_status, 'to_status_display': e.get_to_status_display(),
             'changed_at': e.changed_at, 'event': e.from_status != e.to_status}
            for e in obj.status_log.all()
        ]


# --- Administration -------------------------------------------------------------------------------

class AdminRemittanceListSerializer(serializers.ModelSerializer):
    """One row of the administrator's inbox."""

    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    delivery_method_display = serializers.CharField(source='get_delivery_method_display', read_only=True)
    sender_email = serializers.EmailField(source='sender.email', read_only=True)
    payment_status = serializers.CharField(source='payment.status', read_only=True)
    payment_provider = serializers.CharField(source='payment.provider', read_only=True)
    has_proof = serializers.SerializerMethodField()

    class Meta:
        model = Remittance
        fields = (
            'tracking_id', 'status', 'status_display', 'amount_sent', 'currency', 'amount_cup', 'is_vip_rate',
            'sender_email', 'recipient_name', 'delivery_method_display', 'payment_method',
            'payment_method_display', 'payment_provider', 'payment_status', 'has_proof', 'created_at', 'updated_at',
        )
        read_only_fields = fields

    def get_has_proof(self, obj) -> bool:
        return bool(obj.payment_reference or obj.payment_proof)


class AdminStatusLogSerializer(serializers.ModelSerializer):
    changed_by_email = serializers.EmailField(source='changed_by.email', read_only=True, default=None)
    from_status_display = serializers.SerializerMethodField()
    to_status_display = serializers.CharField(source='get_to_status_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)

    class Meta:
        model = RemittanceStatusLog
        fields = (
            'from_status', 'from_status_display', 'to_status', 'to_status_display', 'source', 'source_display',
            'changed_by_email', 'note', 'changed_at',
        )
        read_only_fields = fields

    def get_from_status_display(self, obj) -> str:
        return obj.get_from_status_display() if obj.from_status else ''


class AdminPaymentSerializer(serializers.Serializer):
    reference = serializers.UUIDField()
    method = serializers.CharField()
    provider = serializers.CharField()
    status = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    instructions = serializers.CharField()
    external_reference = serializers.CharField()
    confirmed_at = serializers.DateTimeField()
    confirmed_by_email = serializers.EmailField(source='confirmed_by.email', default=None)


class AdminRemittanceDetailSerializer(RemittanceSerializer):
    """Everything an administrator needs to verify and decide: who sent it, the payment, the
    proof, the full history and which actions are possible now."""

    sender = serializers.SerializerMethodField()
    payment = AdminPaymentSerializer(read_only=True)
    payment_reference = serializers.CharField(read_only=True)
    has_proof_file = serializers.SerializerMethodField()
    status_log = AdminStatusLogSerializer(many=True, read_only=True)
    allowed_actions = serializers.SerializerMethodField()

    class Meta(RemittanceSerializer.Meta):
        fields = RemittanceSerializer.Meta.fields + (
            'sender', 'payment', 'payment_reference', 'has_proof_file', 'status_log', 'allowed_actions',
        )
        read_only_fields = fields

    def get_sender(self, obj) -> dict:
        user = obj.sender
        return {
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'membership_status': user.profile.membership_status,
        }

    def get_has_proof_file(self, obj) -> bool:
        return bool(obj.payment_proof)

    def get_allowed_actions(self, obj) -> list[str]:
        return allowed_actions(obj)


class StatusChangeSerializer(serializers.Serializer):
    """PATCH body. PENDING_PAYMENT is never a target: nothing goes back to it."""

    status = serializers.ChoiceField(
        choices=[Remittance.Status.PAID, Remittance.Status.COMPLETED, Remittance.Status.CANCELLED],
        error_messages={'required': 'Indica el nuevo estado.', 'invalid_choice': 'Estado de destino no válido.'},
    )
    note = serializers.CharField(required=False, allow_blank=True, max_length=500, default='',
                                 error_messages={'max_length': 'La nota admite máximo 500 caracteres.'})


# --- Payment proof --------------------------------------------------------------------------------

# What a real file of each kind starts with. The name the customer gives is not trusted.
SIGNATURES = {
    '.jpg': (b'\xff\xd8\xff',),
    '.jpeg': (b'\xff\xd8\xff',),
    '.png': (b'\x89PNG\r\n\x1a\n',),
    '.pdf': (b'%PDF-',),
}


class PaymentProofSerializer(serializers.Serializer):
    reference = serializers.CharField(
        required=False, allow_blank=True, max_length=120,
        error_messages={'max_length': 'La referencia admite máximo 120 caracteres.'},
    )
    file = serializers.FileField(required=False, allow_empty_file=False, error_messages={
        'invalid': 'El archivo no es válido.', 'empty': 'El archivo está vacío.', 'max_length': 'El nombre del archivo es demasiado largo.',
    })

    def validate_file(self, upload):
        if upload.size > settings.PAYMENT_PROOF_MAX_BYTES:
            limit_mb = settings.PAYMENT_PROOF_MAX_BYTES / (1024 * 1024)
            raise serializers.ValidationError(f'El archivo es demasiado grande (máximo {limit_mb:g} MB).')

        extension = PurePath(upload.name).suffix.lower()
        if extension not in SIGNATURES:
            raise serializers.ValidationError('Formato no admitido. Sube una imagen JPG o PNG, o un PDF.')

        head = upload.read(8)
        upload.seek(0)
        if not any(head.startswith(signature) for signature in SIGNATURES[extension]):
            raise serializers.ValidationError('El contenido no coincide con el tipo de archivo.')
        return upload

    def validate(self, attrs):
        attrs['reference'] = ' '.join(attrs.get('reference', '').split())
        if not attrs['reference'] and 'file' not in attrs:
            raise serializers.ValidationError('Indica la referencia del pago o adjunta el comprobante.')
        return attrs
