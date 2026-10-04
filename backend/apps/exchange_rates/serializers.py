from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Currency, ExchangeRate, ExchangeRateHistory
from .services import effective_rate, save_exchange_rate, spread_for

NUMBER_ERRORS = {
    'invalid': 'Ingresa un número válido.',
    'required': 'Este campo es obligatorio.',
    'null': 'Este campo es obligatorio.',
    'max_decimal_places': 'Máximo {max_decimal_places} decimales.',
    'max_whole_digits': 'El número es demasiado grande.',
    'max_digits': 'El número es demasiado grande.',
}


class ExchangeRateSerializer(serializers.ModelSerializer):
    """Admin CRUD of the base rate and margins (HU-ADM-01).

    Decimals travel as strings so no precision is lost in JSON.
    """

    currency = serializers.ChoiceField(
        choices=Currency.choices,
        error_messages={'invalid_choice': 'Moneda no válida. Usa USD o EUR.', 'required': 'Este campo es obligatorio.'},
    )
    base_rate = serializers.DecimalField(
        max_digits=18, decimal_places=6, min_value=Decimal('0.000001'),
        error_messages={**NUMBER_ERRORS, 'min_value': 'La tasa base debe ser mayor que 0.'},
    )
    standard_spread_percent = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=Decimal('0'), max_value=Decimal('99.99'),
        error_messages={
            **NUMBER_ERRORS,
            'min_value': 'El margen no puede ser negativo.',
            'max_value': 'El margen debe ser menor que 100 por ciento.',
        },
    )
    vip_spread_percent = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=Decimal('0'), max_value=Decimal('99.99'),
        error_messages={
            **NUMBER_ERRORS,
            'min_value': 'El margen no puede ser negativo.',
            'max_value': 'El margen debe ser menor que 100 por ciento.',
        },
    )
    effective_rate_standard = serializers.SerializerMethodField()
    effective_rate_vip = serializers.SerializerMethodField()
    updated_by_email = serializers.EmailField(source='updated_by.email', read_only=True, default=None)

    class Meta:
        model = ExchangeRate
        fields = (
            'id', 'currency', 'target_currency', 'base_rate',
            'standard_spread_percent', 'vip_spread_percent', 'is_active',
            'effective_rate_standard', 'effective_rate_vip',
            'created_at', 'updated_at', 'updated_by_email',
        )
        read_only_fields = ('id', 'target_currency', 'created_at', 'updated_at')
        # DRF would derive an English "unique set" validator from the model's
        # UniqueConstraint; validate() below enforces the same rule in Spanish.
        validators = []

    def get_effective_rate_standard(self, obj) -> str:
        return str(effective_rate(obj, is_vip=False))

    def get_effective_rate_vip(self, obj) -> str:
        return str(effective_rate(obj, is_vip=True))

    def validate_currency(self, value):
        if self.instance and value != self.instance.currency:
            raise serializers.ValidationError('No se puede cambiar la moneda de una tasa existente.')
        return value

    def validate(self, attrs):
        instance = self.instance

        def current(name, default=None):
            return attrs.get(name, getattr(instance, name) if instance else default)

        if current('vip_spread_percent') > current('standard_spread_percent'):
            raise serializers.ValidationError(
                {'vip_spread_percent': 'El margen VIP no puede ser mayor que el margen estándar.'},
            )

        currency, is_active = current('currency'), current('is_active', True)
        others = ExchangeRate.objects.filter(currency=currency, is_active=True)
        if instance:
            others = others.exclude(pk=instance.pk)
        if is_active and others.exists():
            raise serializers.ValidationError(
                {'is_active': f'Ya existe una tasa activa para {currency}. Edítala o desactívala primero.'},
            )
        return attrs

    def create(self, validated_data):
        return self._save(ExchangeRate(**validated_data))

    def update(self, instance, validated_data):
        for name, value in validated_data.items():
            setattr(instance, name, value)
        return self._save(instance)

    def _save(self, rate):
        user = self.context['request'].user
        try:
            return save_exchange_rate(rate, user)
        except DjangoValidationError as exc:  # safety net: the rules above should catch it first
            raise serializers.ValidationError(exc.message_dict or exc.messages)


class ExchangeRateHistorySerializer(serializers.ModelSerializer):
    changed_by_email = serializers.EmailField(source='changed_by.email', read_only=True, default=None)

    class Meta:
        model = ExchangeRateHistory
        fields = (
            'id', 'base_rate', 'standard_spread_percent', 'vip_spread_percent',
            'is_active', 'changed_by_email', 'changed_at',
        )
        read_only_fields = fields


class PublicExchangeRateSerializer(serializers.Serializer):
    """What the customer-facing calculator needs, for the viewer who asks.

    `is_vip` comes in the context. The VIP margin of the platform is never
    exposed to someone who is not a member: `effective_rate`, `spread_percent`
    and `is_vip_rate` always describe the rate this viewer would actually get.
    """

    currency = serializers.CharField()
    target_currency = serializers.CharField()
    base_rate = serializers.DecimalField(max_digits=18, decimal_places=6)
    updated_at = serializers.DateTimeField()
    spread_percent = serializers.SerializerMethodField()
    effective_rate = serializers.SerializerMethodField()
    standard_effective_rate = serializers.SerializerMethodField()
    is_vip_rate = serializers.SerializerMethodField()

    def get_spread_percent(self, obj) -> str:
        return str(spread_for(obj, self.context['is_vip']))

    def get_effective_rate(self, obj) -> str:
        return str(effective_rate(obj, self.context['is_vip']))

    def get_standard_effective_rate(self, obj) -> str:
        return str(effective_rate(obj, is_vip=False))

    def get_is_vip_rate(self, obj) -> bool:
        return self.context['is_vip']
