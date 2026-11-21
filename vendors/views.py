from datetime import timedelta
from decimal import Decimal
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import DecimalField, F, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import notify
from catalog.models import Product, ProductImage, ProductVariant
from catalog.services import filter_products
from orders import services
from orders.models import OrderItem, ReturnRequest

from .forms import (ImageForm, PayoutForm, ProductForm, ShipForm, StoreSettingsForm, VariantForm, VendorApplyForm)
from .models import Payout, Vendor

TRANSITIONS = {"pending": ("processing", "cancelled"), "processing": ("shipped", "cancelled"), "shipped": ("delivered",)}


def vendor_required(view):
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        vendor = getattr(request.user, "vendor", None)
        if vendor is None or vendor.status != "approved":
            return redirect("vendor_apply")
        request.vendor = vendor
        return view(request, *args, **kwargs)
    return wrapper


@login_required
def apply(request):
    vendor = getattr(request.user, "vendor", None)
    if vendor and vendor.status == "approved":
        return redirect("vendor_dashboard")
    form = None
    if vendor is None:
        form = VendorApplyForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            v = form.save(commit=False)
            v.user = request.user
            v.save()
            messages.success(request, "Application submitted! An admin will review your store shortly.")
            return redirect("vendor_apply")
    return render(request, "vendors/apply.html", {"vendor": vendor, "form": form})


@vendor_required
def dashboard(request):
    v = request.vendor
    items = v.order_items.all()
    since = timezone.now() - timedelta(days=30)
    ctx = {
        "vendor": v,
        "gross_30d": items.filter(order__created__gte=since).exclude(status__in=["cancelled", "returned"]).aggregate(
            s=Sum(F("price") * F("quantity"), output_field=DecimalField(max_digits=12, decimal_places=2)))["s"] or Decimal("0"),
        "orders_to_ship": items.filter(status__in=["pending", "processing"]).count(),
        "product_count": v.products.count(),
        "low_stock": v.products.filter(stock__lte=5, is_active=True)[:6],
        "recent": items.select_related("order").order_by("-order__created")[:8],
        "open_returns": ReturnRequest.objects.filter(item__vendor=v, status="requested").count(),
        "top_products": items.exclude(status__in=["cancelled", "returned"]).values("name").annotate(
            units=Sum("quantity")).order_by("-units")[:5],
    }
    return render(request, "vendors/dashboard.html", ctx)


@vendor_required
def product_list(request):
    qs = request.vendor.products.select_related("category")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(name__icontains=q)
    page = Paginator(qs, 15).get_page(request.GET.get("page"))
    return render(request, "vendors/products.html", {"page": page, "q": q})


@vendor_required
def product_create(request):
    form = ProductForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        p = form.save(commit=False)
        p.vendor = request.vendor
        p.save()
        messages.success(request, "Product created. You can now add variants and more images.")
        return redirect("vendor_product_edit", pk=p.pk)
    return render(request, "vendors/product_form.html", {"form": form, "product": None})


@vendor_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk, vendor=request.vendor)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Product saved.")
        return redirect("vendor_product_edit", pk=pk)
    return render(request, "vendors/product_form.html", {
        "form": form, "product": product, "variant_form": VariantForm(), "image_form": ImageForm(),
        "variants": product.variants.all(), "gallery": product.images.all()})


@vendor_required
@require_POST
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk, vendor=request.vendor)
    if product.order_items.exists():  # keep history intact: hide instead of delete
        product.is_active = False
        product.save(update_fields=["is_active"])
        messages.info(request, "Product has past orders, so it was hidden instead of deleted.")
    else:
        product.delete()
        messages.success(request, "Product deleted.")
    return redirect("vendor_products")


@vendor_required
@require_POST
def variant_add(request, pk):
    product = get_object_or_404(Product, pk=pk, vendor=request.vendor)
    form = VariantForm(request.POST)
    if form.is_valid():
        v = form.save(commit=False)
        v.product = product
        v.save()
        messages.success(request, "Variant added.")
    else:
        messages.error(request, "Invalid variant: " + "; ".join(sum(form.errors.values(), [])))
    return redirect("vendor_product_edit", pk=pk)


@vendor_required
@require_POST
def variant_delete(request, pk):
    variant = get_object_or_404(ProductVariant, pk=pk, product__vendor=request.vendor)
    product_id = variant.product_id
    variant.delete()
    return redirect("vendor_product_edit", pk=product_id)


@vendor_required
@require_POST
def image_add(request, pk):
    product = get_object_or_404(Product, pk=pk, vendor=request.vendor)
    form = ImageForm(request.POST, request.FILES)
    if form.is_valid():
        img = form.save(commit=False)
        img.product = product
        img.save()
        messages.success(request, "Image added.")
    else:
        messages.error(request, "Please choose a valid image file.")
    return redirect("vendor_product_edit", pk=pk)


@vendor_required
@require_POST
def image_delete(request, pk):
    img = get_object_or_404(ProductImage, pk=pk, product__vendor=request.vendor)
    product_id = img.product_id
    img.delete()
    return redirect("vendor_product_edit", pk=product_id)


@vendor_required
def orders(request):
    qs = request.vendor.order_items.select_related("order").order_by("-order__created")
    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)
    page = Paginator(qs, 15).get_page(request.GET.get("page"))
    return render(request, "vendors/orders.html", {"page": page, "status": status, "transitions": TRANSITIONS})


@vendor_required
@require_POST
def order_item_update(request, pk):
    item = get_object_or_404(OrderItem.objects.select_related("order"), pk=pk, vendor=request.vendor)
    form = ShipForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Invalid update.")
        return redirect("vendor_orders")
    new = form.cleaned_data["status"]
    order = item.order
    if new not in TRANSITIONS.get(item.status, ()):
        messages.error(request, f"Cannot move an item from {item.status} to {new}.")
    elif order.payment_method == "card" and order.payment_status == "unpaid":
        messages.error(request, "The customer has not paid for this order yet.")
    elif new == "cancelled":
        services.cancel_item(item)
        notify(order.user, f"{item.name} in order {order.order_number} was cancelled by the seller.", f"/orders/{order.order_number}/")
        messages.success(request, "Item cancelled and stock restored.")
    else:
        item.status = new
        if new == "shipped":
            item.carrier = form.cleaned_data["carrier"]
            item.tracking_number = form.cleaned_data["tracking_number"]
            item.shipped_at = timezone.now()
        if new == "delivered":
            item.delivered_at = timezone.now()
        item.save()
        order.refresh_status()
        notify(order.user, f"{item.name} in order {order.order_number} is now {new}.", f"/orders/{order.order_number}/")
        messages.success(request, f"Item marked as {new}.")
    return redirect("vendor_orders")


@vendor_required
def returns(request):
    items = ReturnRequest.objects.filter(item__vendor=request.vendor).select_related("item", "item__order", "user")
    return render(request, "vendors/returns.html", {"returns": items})


@vendor_required
@require_POST
def return_resolve(request, pk):
    ret = get_object_or_404(ReturnRequest, pk=pk, item__vendor=request.vendor)
    try:
        services.resolve_return(ret, approve=request.POST.get("action") == "approve")
        messages.success(request, "Return updated.")
    except services.OrderError as exc:
        messages.error(request, str(exc))
    return redirect("vendor_returns")


@vendor_required
def payouts(request):
    return render(request, "vendors/payouts.html", {
        "vendor": request.vendor, "payouts": request.vendor.payouts.all(), "min_payout": settings.MIN_PAYOUT,
        "form": PayoutForm()})


@vendor_required
@require_POST
def payout_request(request):
    form = PayoutForm(request.POST)
    v = request.vendor
    if form.is_valid():
        amount = form.cleaned_data["amount"]
        if amount < Decimal(settings.MIN_PAYOUT):
            messages.error(request, f"Minimum payout is {settings.CURRENCY_SYMBOL}{settings.MIN_PAYOUT}.")
        elif amount > v.balance:
            messages.error(request, "Amount exceeds your available balance.")
        else:
            Payout.objects.create(vendor=v, amount=amount)
            messages.success(request, "Payout requested. The marketplace will process it soon.")
    return redirect("vendor_payouts")


@vendor_required
def store_settings(request):
    form = StoreSettingsForm(request.POST or None, request.FILES or None, instance=request.vendor)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Store settings saved.")
        return redirect("vendor_settings")
    return render(request, "vendors/settings.html", {"form": form})


def storefront(request, slug):
    vendor = get_object_or_404(Vendor, slug=slug, status="approved")
    qs = filter_products(request.GET, vendor=vendor)
    page = Paginator(qs, settings.PAGE_SIZE).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "vendors/storefront.html", {"vendor": vendor, "page": page, "querystring": params.urlencode(),
                                                      "sort": request.GET.get("sort", "newest")})
