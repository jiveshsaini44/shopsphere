from django.conf import settings
from django.db import models
from django.db.models import Avg, Count, Sum
from django.urls import reverse

from core.utils import unique_slug


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    icon = models.CharField(max_length=8, blank=True, help_text="An emoji shown on cards")

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Category, self.name, self)
        super().save(*args, **kwargs)

    def descendant_ids(self):
        ids, frontier = [self.pk], [self.pk]
        while frontier:
            frontier = list(Category.objects.filter(parent_id__in=frontier).values_list("pk", flat=True))
            ids += frontier
        return ids

    def get_absolute_url(self):
        return reverse("category_detail", args=[self.slug])

    def __str__(self):
        return f"{self.parent.name} / {self.name}" if self.parent else self.name


class ProductQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True, vendor__status="approved")


class Product(models.Model):
    vendor = models.ForeignKey("vendors.Vendor", on_delete=models.CASCADE, related_name="products")
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="products")
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_at_price = models.DecimalField("Original price", max_digits=10, decimal_places=2, null=True, blank=True,
                                           help_text="Shown struck-through to advertise a discount")
    stock = models.PositiveIntegerField(default=0, help_text="Auto-synced from variants when variants exist")
    sku = models.CharField(max_length=60, blank=True)
    image = models.ImageField(upload_to="products/", blank=True)
    is_active = models.BooleanField(default=True)
    featured = models.BooleanField(default=False)
    views = models.PositiveIntegerField(default=0)
    avg_rating = models.FloatField(default=0)
    review_count = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-created"]
        indexes = [models.Index(fields=["is_active", "-created"])]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Product, self.name, self)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("product_detail", args=[self.slug])

    @property
    def discount_percent(self):
        if self.compare_at_price and self.compare_at_price > self.price:
            return int(round((1 - self.price / self.compare_at_price) * 100))
        return 0

    @property
    def in_stock(self):
        return self.stock > 0

    def sync_stock(self):
        if self.variants.exists():
            self.stock = self.variants.aggregate(s=Sum("stock"))["s"] or 0
            self.save(update_fields=["stock"])

    def update_rating(self):
        agg = self.reviews.aggregate(a=Avg("rating"), c=Count("id"))
        self.avg_rating = round(agg["a"] or 0, 2)
        self.review_count = agg["c"] or 0
        self.save(update_fields=["avg_rating", "review_count"])

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/gallery/")
    alt = models.CharField(max_length=150, blank=True)


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField(max_length=100, help_text="e.g. Size M / Red")
    sku = models.CharField(max_length=60, blank=True)
    price_delta = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Added to the base price")
    stock = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["id"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.product.sync_stock()

    def delete(self, *args, **kwargs):
        product = self.product
        super().delete(*args, **kwargs)
        product.sync_stock()

    @property
    def price(self):
        return self.product.price + self.price_delta

    def __str__(self):
        return f"{self.product.name} - {self.name}"


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(choices=[(i, f"{i} star{'s' if i > 1 else ''}") for i in range(1, 6)])
    title = models.CharField(max_length=120, blank=True)
    body = models.TextField(blank=True)
    verified_purchase = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
        constraints = [models.UniqueConstraint(fields=["product", "user"], name="one_review_per_user_product")]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.product.update_rating()

    def delete(self, *args, **kwargs):
        product = self.product
        super().delete(*args, **kwargs)
        product.update_rating()


class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishlist")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="wishlisted")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
        constraints = [models.UniqueConstraint(fields=["user", "product"], name="unique_wishlist_item")]
