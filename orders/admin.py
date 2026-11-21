from django.contrib import admin

from .models import Coupon, Order, OrderItem, ReturnRequest


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "variant", "vendor", "name", "price", "quantity", "commission_rate", "vendor_earning")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "user", "status", "payment_method", "payment_status", "total", "created")
    list_filter = ("status", "payment_status", "payment_method")
    search_fields = ("order_number", "user__username", "user__email")
    inlines = [OrderItemInline]
    date_hierarchy = "created"


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "discount_type", "value", "min_order", "used_count", "max_uses", "active", "vendor")
    list_filter = ("active", "discount_type")


@admin.register(ReturnRequest)
class ReturnAdmin(admin.ModelAdmin):
    list_display = ("item", "user", "status", "created")
    list_filter = ("status",)
