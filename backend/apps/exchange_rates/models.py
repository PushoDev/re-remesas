from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Currency(models.TextChoices):
    USD = 'USD', 'Dólar estadounidense'
    EUR = 'EUR', 'Euro'


class ExchangeRate(models.Model):
    """Base rate and platform margins for one currency pair (HU-ADM-01).

    The effective rate a customer gets is `base_rate` minus the spread:
    `standard_spread_percent` for everyone, `vip_spread_percent` (lower) for
    members. Only one rate per pair can be active at a time.
    """

    TARGET_CURRENCY = 'CUP'

    currency = models.CharField(max_length=3, choices=Currency.choices)
    target_currency = models.CharField(max_length=3, default=TARGET_CURRENCY, editable=False)
    base_rate = models.DecimalField(max_digits=18, decimal_places=6)
    standard_spread_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))
    vip_spread_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        ordering = ['currency', '-is_active', '-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['currency', 'target_currency'],
                condition=Q(is_active=True),
                name='one_active_rate_per_pair',
            ),
            models.CheckConstraint(condition=Q(base_rate__gt=0), name='rate_base_positive'),
            models.CheckConstraint(
                condition=Q(standard_spread_percent__gte=0, standard_spread_percent__lt=100),
                name='rate_standard_spread_range',
            ),
            models.CheckConstraint(
                condition=Q(vip_spread_percent__gte=0, vip_spread_percent__lt=100),
                name='rate_vip_spread_range',
            ),
            # A member never pays a bigger margin than a standard customer.
            models.CheckConstraint(
                condition=Q(vip_spread_percent__lte=F('standard_spread_percent')),
                name='rate_vip_spread_not_above_standard',
            ),
        ]

    def __str__(self):
        return f'{self.currency}→{self.target_currency} {self.base_rate}'


class ExchangeRateHistory(models.Model):
    """Append-only snapshot written on every create/update of an ExchangeRate."""

    rate = models.ForeignKey(ExchangeRate, on_delete=models.CASCADE, related_name='history')
    base_rate = models.DecimalField(max_digits=18, decimal_places=6)
    standard_spread_percent = models.DecimalField(max_digits=5, decimal_places=2)
    vip_spread_percent = models.DecimalField(max_digits=5, decimal_places=2)
    is_active = models.BooleanField()
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at', '-id']
        verbose_name_plural = 'exchange rate history'
