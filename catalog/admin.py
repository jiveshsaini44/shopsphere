from django.contrib import admin

from .models import Category, Product, ProductImage, ProductVariant, Review, Wishlist


class VariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


class ImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "slug")
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "vendor", "category", "price", "stock", "is_active", "featured", "avg_rating")
    list_filter = ("is_active", "featured", "category", "vendor")
    search_fields = ("name", "sku", "vendor__store_name")
    list_editable = ("is_active", "featured")
    inlines = [VariantInline, ImageInline]
    actions = ["deactivate", "activate"]

    @admin.action(description="Deactivate selected products")
    def deactivate(self, request, qs):
        qs.update(is_active=False)

    @admin.action(description="Activate selected products")
    def activate(self, request, qs):
        qs.update(is_active=True)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "rating", "verified_purchase", "created")
    list_filter = ("rating", "verified_purchase")


admin.site.register(Wishlist)
