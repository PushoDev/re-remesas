import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class PaymentMethod(models.TextChoices):
    """What the customer picks. Which provider handles it is decided in providers.registry."""

    STRIPE = 'STRIPE', 'Stripe'
    PAYPAL = 'PAYPAL', 'PayPal'
    WISE = 'WISE', 'Wise'
    MERCADO_PAGO = 'MERCADO_PAGO', 'Mercado Pago'
    ENZONA = 'ENZONA', 'EnZona'
    ZELLE = 'ZELLE', 'Zelle'
    CASH = 'CASH', 'Efectivo'


class PaymentPurpose(models.TextChoices):
    MEMBERSHIP = 'MEMBERSHIP', 'Membresía'
    REMITTANCE = 'REMITTANCE', 'Remesa'
    RECHARGE = 'RECHARGE', 'Recarga'


class PaymentStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pendiente'
    SUCCEEDED = 'SUCCEEDED', 'Pagado'
    FAILED = 'FAILED', 'Fallido'


class Payment(models.Model):
    """A payment request for something (membership, remittance, recharge).

    It knows nothing about what it pays for beyond `purpose` + `target_id`;
    when it succeeds, a handler registered for that purpose does the work.
    `amount` is the price snapshot taken when the payment was created.
    """

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='payments')
    purpose = models.CharField(max_length=20, choices=PaymentPurpose.choices)
    target_id = models.PositiveBigIntegerField(null=True, blank=True)
    method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    provider = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    status = models.CharField(max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    external_reference = models.CharField(max_length=100, blank=True)
    instructions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    # Set when an administrator settles a manual payment (Zelle, Wise, cash); null for gateway payments.
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['user', '-created_at'])]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name='payment_amount_positive'),
            models.UniqueConstraint(
                fields=['provider', 'external_reference'],
                condition=~Q(external_reference=''),
                name='payment_unique_external_reference',
            ),
        ]

    def __str__(self):
        return f'{self.purpose} {self.amount} {self.currency} [{self.status}]'
