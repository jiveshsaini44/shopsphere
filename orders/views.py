import hmac
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import notify

from . import services
from .forms import CheckoutForm, MockPayForm, ReturnForm
from .models import Order, OrderItem, ReturnRequest


def cart_page(request):
    return render(request, "orders/cart.html")


@login_required
def checkout(request):
    cart = services.get_cart(request)
    if not cart.items.exists():
        messages.info(request, "Your cart is empty.")
        return redirect("cart")
    totals = services.cart_totals(cart, request.session.get("coupon", ""))
    addresses = list(request.user.addresses.all())
    form = CheckoutForm(request.POST or None, initial={"payment_method": "card"})
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        addr = None
        if d.get("address_id"):
            saved = next((a for a in addresses if a.pk == d["address_id"]), None)
            if saved is None:
                return HttpResponseBadRequest("Invalid address")
            addr = {"full_name": saved.full_name, "phone": saved.phone, "line1": saved.line1, "line2": saved.line2,
                    "city": saved.city, "state": saved.state, "postal_code": saved.postal_code, "country": saved.country}
        else:
            addr = {k: d.get(k, "") for k in ("full_name", "phone", "line1", "line2", "city", "state", "postal_code", "country")}
            if d.get("save_address"):
                request.user.addresses.create(is_default=not addresses, **addr)
        try:
            order = services.place_order(request.user, cart, addr, d["payment_method"], request.session.get("coupon", ""))
        except services.OrderError as exc:
            messages.error(request, str(exc))
            return redirect("cart")
        request.session.pop("coupon", None)
        if order.payment_method == "card":
            return redirect("mock_pay", number=order.order_number)
        messages.success(request, "Order placed! You will pay on delivery.")
        return redirect("order_detail", number=order.order_number)
    return render(request, "orders/checkout.html", {"form": form, "addresses": addresses, "t": totals})


@login_required
def mock_pay(request, number):
    order = get_object_or_404(Order, order_number=number, user=request.user)
    if order.payment_status != "unpaid" or order.status == "cancelled":
        return redirect("order_detail", number=number)
    form = MockPayForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ok, result = services.mock_charge(form.cleaned_data["card_number"])
        if ok:
            services.mark_paid(order, result)
            messages.success(request, "Payment successful. Thank you!")
            return redirect("order_detail", number=number)
        messages.error(request, result)
    return render(request, "orders/mock_pay.html", {"order": order, "form": form})


@csrf_exempt
@require_POST
def payment_webhook(request):
    """Entry point for a real gateway (Stripe/Razorpay...). Verifies a shared-secret HMAC, then marks the order paid.
    Body: {"order_number": "...", "reference": "..."}; header X-Signature = hex HMAC-SHA256(body, PAYMENT_WEBHOOK_SECRET)."""
    import hashlib
    expected = hmac.new(settings.PAYMENT_WEBHOOK_SECRET.encode(), request.body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, request.headers.get("X-Signature", "")):
        return HttpResponse(status=401)
    try:
        data = json.loads(request.body)
        order = Order.objects.get(order_number=data["order_number"])
    except (ValueError, KeyError, Order.DoesNotExist):
        return HttpResponseBadRequest("bad payload")
    if order.payment_status == "unpaid":
        services.mark_paid(order, data.get("reference", "webhook"))
    return HttpResponse("ok")


@login_required
def order_list(request):
    orders = request.user.orders.prefetch_related("items")
    return render(request, "orders/order_list.html", {"orders": orders})


@login_required
def order_detail(request, number):
    order = get_object_or_404(Order.objects.prefetch_related("items__vendor"), order_number=number, user=request.user)
    steps = ["pending", "processing", "shipped", "delivered"]
    idx = steps.index(order.status) if order.status in steps else -1
    return render(request, "orders/order_detail.html", {"order": order, "steps": steps, "step_idx": idx,
                                                        "return_form": ReturnForm()})


@login_required
def invoice(request, number):
    order = get_object_or_404(Order.objects.prefetch_related("items"), order_number=number, user=request.user)
    return render(request, "orders/invoice.html", {"order": order})


@login_required
@require_POST
def order_cancel(request, number):
    order = get_object_or_404(Order, order_number=number, user=request.user)
    try:
        services.cancel_order(order)
        messages.success(request, "Order cancelled." + (" Your refund is on its way." if order.payment_status != "unpaid" else ""))
    except services.OrderError as exc:
        messages.error(request, str(exc))
    return redirect("order_detail", number=number)


@login_required
@require_POST
def return_request(request, item_id):
    item = get_object_or_404(OrderItem, pk=item_id, order__user=request.user)
    form = ReturnForm(request.POST)
    if not item.can_return:
        messages.error(request, "This item is not eligible for return.")
    elif form.is_valid():
        ReturnRequest.objects.create(item=item, user=request.user, reason=form.cleaned_data["reason"])
        notify(item.vendor.user, f"Return requested for {item.name} (order {item.order.order_number}).", "/vendor/returns/")
        messages.success(request, "Return requested. The seller will review it shortly.")
    else:
        messages.error(request, "Please tell us why you are returning the item.")
    return redirect("order_detail", number=item.order.order_number)
