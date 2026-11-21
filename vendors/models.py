from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.urls import reverse

from core.utils import unique_slug


def _default_commission():
    return Decimal(settings.DEFAULT_COMMISSION)


class Vendor(models.Model):
    PENDING, APPROVED, SUSPENDED = "pending", "approved", "suspended"
    STATUS = [(PENDING, "Pending review"), (APPROVED, "Approved"), (SUSPENDED, "Suspended")]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vendor")
    store_name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to="vendors/", blank=True)
    support_email = models.EmailField(blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default=PENDING)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=_default_commission,
                                          help_text="Percent the marketplace keeps from each sale")
    created = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Vendor, self.store_name, self)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("storefront", args=[self.slug])

    # --- money -----------------------------------------------------------------
    @property
    def earned(self):
        """Vendor share of delivered items (only delivered sales are payable)."""
        return self.order_items.filter(status="delivered").aggregate(s=Sum("vendor_earning"))["s"] or Decimal("0")

    @property
    def paid_out(self):
        return self.payouts.exclude(status="rejected").aggregate(s=Sum("amount"))["s"] or Decimal("0")

    @property
    def balance(self):
        return self.earned - self.paid_out

    def __str__(self):
        return self.store_name


class Payout(models.Model):
    REQUESTED, PAID, REJECTED = "requested", "paid", "rejected"
    STATUS = [(REQUESTED, "Requested"), (PAID, "Paid"), (REJECTED, "Rejected")]

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="payouts")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS, default=REQUESTED)
    note = models.CharField(max_length=200, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.vendor} - {self.amount} ({self.status})"
