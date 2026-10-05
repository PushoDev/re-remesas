import uuid
from pathlib import PurePath

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.exchange_rates.models import Currency
from apps.payments.models import PaymentMethod


def proof_path(instance, filename):
    """A random name under the remittance's folder: the customer's file name is not trusted or kept."""
    extension = PurePath(filename).suffix.lower()
    return f'payment_proofs/{instance.tracking_id}/{uuid.uuid4().hex}{extension}'


class Remittance(models.Model):
    """A request to send money to someone in Cuba (HU-REM-01).

    All the money figures are a snapshot taken when it was created: changing or
    deactivating an exchange rate later never alters an existing remittance.
    """

    class DeliveryMethod(models.TextChoices):
        CASH_DELIVERY = 'CASH_DELIVERY', 'Entrega de efectivo en Cuba'
        LOCAL_TRANSFER = 'LOCAL_TRANSFER', 'Transferencia local en Cuba'

    class Status(models.TextChoices):
        PENDING_PAYMENT = 'PENDING_PAYMENT', 'Pendiente de pago'
        PAID = 'PAID', 'Pagado'
        COMPLETED = 'COMPLETED', 'Completado'
        CANCELLED = 'CANCELLED', 'Cancelado'

    # What a customer (and support) quotes: human-readable, unique, not the database id.
    tracking_id = models.CharField(max_length=20, unique=True, editable=False)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='remittances')

    amount_sent = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=Currency.choices)

    # Snapshot of the rate applied (see exchange_rates.services.convert).
    base_rate_used = models.DecimalField(max_digits=18, decimal_places=6)
    spread_percent_used = models.DecimalField(max_digits=5, decimal_places=2)
    effective_rate_used = models.DecimalField(max_digits=18, decimal_places=4)
    amount_cup = models.DecimalField(max_digits=14, decimal_places=2)
    is_vip_rate = models.BooleanField(default=False)

    recipient_name = models.CharField(max_length=120)
    recipient_phone = models.CharField(max_length=13)  # +53XXXXXXXX
    recipient_address = models.CharField(max_length=255, blank=True)  # cash delivery
    recipient_account = models.CharField(max_length=40, blank=True)  # local transfer
    delivery_method = models.CharField(max_length=20, choices=DeliveryMethod.choices)

    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    payment = models.OneToOneField('payments.Payment', on_delete=models.PROTECT, related_name='remittance')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_PAYMENT)

    # What the customer gives so an administrator can verify a manual payment.
    payment_reference = models.CharField(max_length=120, blank=True)
    payment_proof = models.FileField(upload_to=proof_path, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['sender', '-created_at']), models.Index(fields=['status'])]
        constraints = [
            models.CheckConstraint(condition=Q(amount_sent__gt=0), name='remittance_amount_positive'),
            models.CheckConstraint(condition=Q(effective_rate_used__gt=0), name='remittance_rate_positive'),
            models.CheckConstraint(condition=Q(amount_cup__gt=0), name='remittance_cup_positive'),
            # The data needed to deliver depends on how it is delivered.
            models.CheckConstraint(
                condition=(
                    Q(delivery_method='CASH_DELIVERY') & ~Q(recipient_address='')
                    | Q(delivery_method='LOCAL_TRANSFER') & ~Q(recipient_account='')
                ),
                name='remittance_delivery_data_present',
            ),
        ]

    def __str__(self):
        return f'{self.tracking_id} {self.amount_sent} {self.currency} [{self.status}]'


class RemittanceStatusLog(models.Model):
    """Append-only trail of every state a remittance has been in, and who/what moved it."""

    class Source(models.TextChoices):
        CUSTOMER = 'CUSTOMER', 'Cliente'
        PAYMENT = 'PAYMENT', 'Pago'
        ADMIN = 'ADMIN', 'Administrador'

    remittance = models.ForeignKey(Remittance, on_delete=models.CASCADE, related_name='status_log')
    from_status = models.CharField(max_length=20, choices=Remittance.Status.choices, blank=True)  # blank = creation
    to_status = models.CharField(max_length=20, choices=Remittance.Status.choices)
    source = models.CharField(max_length=10, choices=Source.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )
    note = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['changed_at', 'id']  # chronological: it is a timeline

    def __str__(self):
        return f'{self.remittance_id}: {self.from_status or "∅"} → {self.to_status}'
