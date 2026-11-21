import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class Coupon(models.Model):
    PERCENT, FIXED = "percent", "fixed"
    code = models.CharField(max_length=30, unique=True)
    discount_type = models.CharField(max_length=8, choices=[(PERCENT, "Percent"), (FIXED, "Fixed amount")], default=PERCENT)
    value = models.DecimalField(max_digits=8, decimal_places=2)
    min_order = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    used_count = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    vendor = models.ForeignKey("vendors.Vendor", null=True, blank=True, on_delete=models.CASCADE,
                               help_text="Leave empty for a marketplace-wide coupon")

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def is_valid_now(self):
        now = timezone.now()
        if not self.active:
            return False
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_to and now > self.valid_to:
            return False
        if self.max_uses is not None and self.used_count >= self.max_uses:
            return False
        return True

    def discount_for(self, eligible):
        eligible = Decimal(eligible)
        if self.discount_type == self.PERCENT:
            amount = eligible * self.value / Decimal("100")
        else:
            amount = self.value
        return min(amount, eligible).quantize(Decimal("0.01"))

    def __str__(self):
        return self.code


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="cart")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE)
    variant = models.ForeignKey("catalog.ProductVariant", null=True, blank=True, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    @property
    def unit_price(self):
        return self.product.price + (self.variant.price_delta if self.variant_id else 0)

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def available(self):
        return self.variant.stock if self.variant_id else self.product.stock


def _order_number():
    return "SS-" + timezone.now().strftime("%y%m%d") + "-" + uuid.uuid4().hex[:6].upper()


class Order(models.Model):
    STATUS = [("pending", "Pending"), ("processing", "Processing"), ("shipped", "Shipped"),
              ("delivered", "Delivered"), ("cancelled", "Cancelled")]
    PAYMENT_STATUS = [("unpaid", "Unpaid"), ("paid", "Paid"), ("partially_refunded", "Partially refunded"),
                      ("refunded", "Refunded")]
    PAYMENT_METHODS = [("card", "Credit / debit card"), ("cod", "Cash on delivery")]

    order_number = models.CharField(max_length=24, unique=True, default=_order_number, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(max_length=12, choices=STATUS, default="pending")
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS, default="card")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default="unpaid")
    payment_ref = models.CharField(max_length=80, blank=True)

    ship_name = models.CharField(max_length=120)
    ship_phone = models.CharField(max_length=20)
    ship_line1 = models.CharField(max_length=200)
    ship_line2 = models.CharField(max_length=200, blank=True)
    ship_city = models.CharField(max_length=100)
    ship_state = models.CharField(max_length=100, blank=True)
    ship_postal = models.CharField(max_length=20)
    ship_country = models.CharField(max_length=100)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    refunded_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coupon_code = models.CharField(max_length=30, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return self.order_number

    @property
    def can_cancel(self):
        items = list(self.items.all())
        return bool(items) and self.status != "cancelled" and all(i.status in ("pending", "processing") for i in items)

    def refresh_status(self):
        self.refresh_from_db(fields=["status", "payment_status"])
        statuses = [i.status for i in self.items.all()]
        live = [s for s in statuses if s not in ("cancelled", "returned")]
        if not live:
            new = "cancelled"
        elif all(s == "delivered" for s in live):
            new = "delivered"
        elif any(s in ("shipped", "delivered") for s in live):
            new = "shipped"
        elif any(s == "processing" for s in live):
            new = "processing"
        else:
            new = "pending"
        self.status = new
        if new == "delivered" and self.payment_method == "cod" and self.payment_status == "unpaid":
            self.payment_status = "paid"
        self.save(update_fields=["status", "payment_status"])


class OrderItem(models.Model):
    STATUS = [("pending", "Pending"), ("processing", "Processing"), ("shipped", "Shipped"),
              ("delivered", "Delivered"), ("cancelled", "Cancelled"), ("returned", "Returned")]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", null=True, on_delete=models.SET_NULL, related_name="order_items")
    variant = models.ForeignKey("catalog.ProductVariant", null=True, blank=True, on_delete=models.SET_NULL)
    vendor = models.ForeignKey("vendors.Vendor", on_delete=models.PROTECT, related_name="order_items")
    name = models.CharField(max_length=200)
    variant_name = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    vendor_earning = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=12, choices=STATUS, default="pending")
    carrier = models.CharField(max_length=60, blank=True)
    tracking_number = models.CharField(max_length=80, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    @property
    def line_total(self):
        return self.price * self.quantity

    @property
    def can_return(self):
        from datetime import timedelta
        if self.status != "delivered" or not self.delivered_at:
            return False
        if self.returns.exists():
            return False
        return timezone.now() <= self.delivered_at + timedelta(days=settings.RETURN_WINDOW_DAYS)


class ReturnRequest(models.Model):
    STATUS = [("requested", "Requested"), ("approved", "Approved & refunded"), ("rejected", "Rejected")]
    item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="returns")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reason = models.CharField(max_length=300)
    status = models.CharField(max_length=10, choices=STATUS, default="requested")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
