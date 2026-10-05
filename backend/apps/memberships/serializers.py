from rest_framework import serializers

from apps.payments.models import PaymentMethod
from apps.payments.serializers import PaymentSerializer

from .models import MembershipPlan, Subscription


class MembershipPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipPlan
        fields = (
            'code', 'name', 'period', 'price', 'currency', 'duration_days',
            'recharge_discount_percent', 'benefits',
        )
        read_only_fields = fields


class SubscribeSerializer(serializers.Serializer):
    plan_code = serializers.CharField(error_messages={'required': 'Elige un plan.', 'blank': 'Elige un plan.'})
    payment_method = serializers.ChoiceField(
        choices=PaymentMethod.choices,
        error_messages={'required': 'Elige un medio de pago.', 'invalid_choice': 'Medio de pago no válido.'},
    )

    def validate_plan_code(self, value):
        try:
            return MembershipPlan.objects.get(code=value, is_active=True)
        except MembershipPlan.DoesNotExist:
            raise serializers.ValidationError('Ese plan no está disponible.') from None


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = MembershipPlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = ('id', 'status', 'plan', 'starts_at', 'expires_at', 'created_at')
        read_only_fields = fields


class SubscribeResultSerializer(serializers.Serializer):
    subscription = SubscriptionSerializer()
    payment = PaymentSerializer()
