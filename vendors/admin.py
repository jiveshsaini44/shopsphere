from django.contrib import admin

from accounts.models import notify

from .models import Payout, Vendor


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ("store_name", "user", "status", "commission_rate", "created")
    list_filter = ("status",)
    search_fields = ("store_name", "user__username", "user__email")
    actions = ["approve", "suspend"]

    @admin.action(description="Approve selected vendors")
    def approve(self, request, qs):
        for v in qs:
            v.status = "approved"
            v.save()
            notify(v.user, "Your store was approved. You can start selling!", "/vendor/")

    @admin.action(description="Suspend selected vendors")
    def suspend(self, request, qs):
        qs.update(status="suspended")


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ("vendor", "amount", "status", "created")
    list_filter = ("status",)
    actions = ["mark_paid", "reject"]

    @admin.action(description="Mark selected payouts as paid")
    def mark_paid(self, request, qs):
        for p in qs.filter(status="requested"):
            p.status = "paid"
            p.save()
            notify(p.vendor.user, f"Payout of {p.amount} was sent.", "/vendor/payouts/")

    @admin.action(description="Reject selected payouts")
    def reject(self, request, qs):
        qs.filter(status="requested").update(status="rejected")
