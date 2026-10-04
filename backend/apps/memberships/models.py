from django.conf import settings
from django.db import models
from django.db.models import Q


class MembershipPlan(models.Model):
    """A purchasable VIP plan. The remittance benefit (lower spread) lives in
    ExchangeRate.vip_spread_percent; the plan only carries the recharge discount."""

    class Period(models.TextChoices):
        MONTHLY = 'MONTHLY', 'Mensual'
        ANNUAL = 'ANNUAL', 'Anual'

    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    period = models.CharField(max_length=10, choices=Period.choices)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    duration_days = models.PositiveIntegerField()
    recharge_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    benefits = models.JSONField(default=list, blank=True, help_text='Lista de textos con los beneficios.')
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'price']
        constraints = [
            models.CheckConstraint(condition=Q(price__gt=0), name='plan_price_positive'),
            models.CheckConstraint(condition=Q(duration_days__gt=0), name='plan_duration_positive'),
            models.CheckConstraint(
                condition=Q(recharge_discount_percent__gte=0, recharge_discount_percent__lt=100),
                name='plan_recharge_discount_range',
            ),
        ]

    def __str__(self):
        return f'{self.name} ({self.price} {self.currency})'


class Subscription(models.Model):
    """One purchase of a plan. Created PENDING with its payment; becomes ACTIVE
    only when that payment is confirmed (never by the browser coming back)."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente de pago'
        ACTIVE = 'ACTIVE', 'Activa'
        FAILED = 'FAILED', 'Pago fallido'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='subscriptions')
    plan = models.ForeignKey(MembershipPlan, on_delete=models.PROTECT, related_name='subscriptions')
    payment = models.OneToOneField('payments.Payment', on_delete=models.PROTECT, related_name='subscription')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    # Snapshot taken at purchase time, so editing the plan later changes nothing here.
    duration_days = models.PositiveIntegerField()
    recharge_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    starts_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.user} · {self.plan.code} [{self.status}]'
