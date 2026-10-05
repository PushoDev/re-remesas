import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class RechargePackage(models.Model):
    """Something a customer can top up: plain balance, or a data/voice bundle (HU-TOP-01).

    Prices are in USD. Whether a promotion applies is decided by Promotion, not stored here.
    """

    class Kind(models.TextChoices):
        BALANCE = 'BALANCE', 'Saldo'
        DATA = 'DATA', 'Datos'
        VOICE = 'VOICE', 'Voz'
        COMBO = 'COMBO', 'Combinado datos y voz'

    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    description = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    is_demo = models.BooleanField(default=False, help_text='Paquete de ejemplo, no un precio real de ETECSA.')
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'price']
        constraints = [
            models.CheckConstraint(condition=Q(price__gt=0), name='recharge_package_price_positive'),
        ]

    def __str__(self):
        return f'{self.name} ({self.price} {self.currency})'


class Promotion(models.Model):
    """An ETECSA promotion the backend announces. The server decides if it is current;
    the browser only draws it. It does not change what the customer pays (see DECISIONS)."""

    code = models.SlugField(max_length=40, unique=True)
    title = models.CharField(max_length=80)
    description = models.CharField(max_length=200, blank=True)
    # Null = applies to every package.
    package = models.ForeignKey(
        RechargePackage, null=True, blank=True, on_delete=models.CASCADE, related_name='promotions',
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-starts_at', 'id']
        constraints = [
            models.CheckConstraint(condition=Q(ends_at__gt=F('starts_at')), name='promotion_ends_after_start'),
        ]

    def __str__(self):
        return self.title


class RechargeOrder(models.Model):
    """A top-up bought by a customer. Every money figure is a snapshot taken at creation,
    so changing a package price or a plan discount later never alters an existing order."""

    class Status(models.TextChoices):
        PENDING_PAYMENT = 'PENDING_PAYMENT', 'Pendiente de pago'
        PROCESSING = 'PROCESSING', 'Procesando'
        SUCCESS = 'SUCCESS', 'Exitosa'
        FAILED = 'FAILED', 'Fallida'

    # What the customer's URLs carry: not the database id, which would be guessable.
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='recharge_orders')
    phone_number = models.CharField(max_length=13)  # +53XXXXXXXX
    package = models.ForeignKey(RechargePackage, on_delete=models.PROTECT, related_name='orders')

    price_base = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percent_applied = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    amount_total = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    # The promotion that was current when the order was made (informational), or null.
    promotion_snapshot = models.JSONField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_PAYMENT)
    provider_reference = models.CharField(max_length=100, blank=True)
    provider_message = models.CharField(max_length=200, blank=True)
    payment = models.OneToOneField('payments.Payment', on_delete=models.PROTECT, related_name='recharge_order')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['user', '-created_at']), models.Index(fields=['status'])]
        constraints = [
            models.CheckConstraint(condition=Q(price_base__gt=0), name='recharge_order_base_positive'),
            models.CheckConstraint(condition=Q(amount_total__gt=0), name='recharge_order_total_positive'),
            models.CheckConstraint(
                condition=Q(amount_total__lte=F('price_base')), name='recharge_order_total_not_above_base',
            ),
            models.CheckConstraint(
                condition=Q(discount_percent_applied__gte=0, discount_percent_applied__lt=100),
                name='recharge_order_discount_range',
            ),
        ]

    def __str__(self):
        return f'{self.phone_number} {self.package_id} {self.amount_total} {self.currency} [{self.status}]'
