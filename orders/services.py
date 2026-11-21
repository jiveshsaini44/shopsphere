"""Cart maths, coupon rules, order placement, commission split, refunds, mock payments."""
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from accounts.models import notify
from catalog.models import Product, ProductVariant

from .models import Cart, Coupon, Order, OrderItem

CENT = Decimal("0.01")


class OrderError(Exception):
    pass


def q(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


# ---- cart ---------------------------------------------------------------------
def get_cart(request, create=True):
    if request.user.is_authenticated:
        if not create:
            return Cart.objects.filter(user=request.user).first()
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart
    cart_id = request.session.get("cart_id")
    cart = Cart.objects.filter(pk=cart_id, user__isnull=True).first() if cart_id else None
    if cart is None and create:
        cart = Cart.objects.create()
        request.session["cart_id"] = cart.pk
    return cart


# ---- coupons & totals -----------------------------------------------------------
def validate_coupon(code, lines):
    coupon = Coupon.objects.filter(code__iexact=(code or "").strip(), active=True).first()
    if not coupon:
        return None, "That coupon code is not valid."
    if not coupon.is_valid_now():
        return None, "That coupon has expired or reached its usage limit."
    eligible = sum((l["unit"] * l["qty"] for l in lines if coupon.vendor_id in (None, l["vendor_id"])), Decimal("0"))
    if eligible <= 0:
        return None, "That coupon does not apply to the items in your cart."
    subtotal = sum((l["unit"] * l["qty"] for l in lines), Decimal("0"))
    if subtotal < coupon.min_order:
        return None, f"This coupon needs a minimum order of {settings.CURRENCY_SYMBOL}{coupon.min_order}."
    return coupon, ""


def compute_totals(lines, coupon=None):
    subtotal = q(sum((l["unit"] * l["qty"] for l in lines), Decimal("0")))
    discount = Decimal("0")
    if coupon:
        eligible = sum((l["unit"] * l["qty"] for l in lines if coupon.vendor_id in (None, l["vendor_id"])), Decimal("0"))
        discount = min(coupon.discount_for(eligible), subtotal)
    taxable = subtotal - discount
    if subtotal == 0 or taxable >= Decimal(settings.FREE_SHIPPING_THRESHOLD):
        shipping = Decimal("0")
    else:
        shipping = Decimal(settings.FLAT_SHIPPING)
    tax = q(taxable * Decimal(settings.TAX_RATE))
    return {"subtotal": subtotal, "discount": q(discount), "shipping": q(shipping), "tax": tax,
            "total": q(taxable + shipping + tax)}


def cart_totals(cart, coupon_code=""):
    items = list(cart.items.select_related("product", "product__vendor", "variant")) if cart else []
    lines = [{"vendor_id": i.product.vendor_id, "unit": i.unit_price, "qty": i.quantity} for i in items]
    coupon, message = (None, "")
    if coupon_code and lines:
        coupon, message = validate_coupon(coupon_code, lines)
    totals = compute_totals(lines, coupon)
    totals.update(coupon=coupon, coupon_message=message, items=items, count=sum(i.quantity for i in items))
    return totals


# ---- placing orders -------------------------------------------------------------
@transaction.atomic
def place_order(user, cart, addr, payment_method, coupon_code=""):
    items = list(cart.items.all())
    if not items:
        raise OrderError("Your cart is empty.")
    locked = []
    for it in items:
        product = Product.objects.select_for_update().select_related("vendor").get(pk=it.product_id)
        variant = ProductVariant.objects.select_for_update().get(pk=it.variant_id) if it.variant_id else None
        available = variant.stock if variant else product.stock
        if not product.is_active or product.vendor.status != "approved":
            raise OrderError(f"'{product.name}' is no longer available. Please remove it from your cart.")
        if it.quantity > available:
            raise OrderError(f"Only {available} left of '{product.name}'. Please update your cart.")
        unit = product.price + (variant.price_delta if variant else 0)
        locked.append((it, product, variant, unit))

    lines = [{"vendor_id": p.vendor_id, "unit": unit, "qty": it.quantity} for it, p, v, unit in locked]
    coupon, _ = validate_coupon(coupon_code, lines) if coupon_code else (None, "")
    totals = compute_totals(lines, coupon)

    order = Order.objects.create(
        user=user, payment_method=payment_method, coupon_code=coupon.code if coupon else "",
        ship_name=addr["full_name"], ship_phone=addr["phone"], ship_line1=addr["line1"], ship_line2=addr.get("line2", ""),
        ship_city=addr["city"], ship_state=addr.get("state", ""), ship_postal=addr["postal_code"],
        ship_country=addr.get("country", ""), **totals)

    vendors = {}
    for it, product, variant, unit in locked:
        rate = product.vendor.commission_rate
        line_total = unit * it.quantity
        earning = q(line_total * (Decimal("100") - rate) / Decimal("100"))
        OrderItem.objects.create(
            order=order, product=product, variant=variant, vendor=product.vendor, name=product.name,
            variant_name=variant.name if variant else "", price=q(unit), quantity=it.quantity,
            commission_rate=rate, vendor_earning=earning)
        if variant:
            variant.stock -= it.quantity
            variant.save()
        else:
            product.stock -= it.quantity
            product.save(update_fields=["stock"])
        vendors[product.vendor_id] = product.vendor

    if coupon:
        Coupon.objects.filter(pk=coupon.pk).update(used_count=coupon.used_count + 1)
    cart.items.all().delete()

    notify(user, f"Order {order.order_number} placed. Total {settings.CURRENCY_SYMBOL}{order.total}.", f"/orders/{order.order_number}/")
    for vendor in vendors.values():
        notify(vendor.user, f"New order {order.order_number} contains your products.", "/vendor/orders/")
    send_mail(f"Your {settings.SHOP_NAME} order {order.order_number}",
              f"Hi {user.first_name or user.username},\n\nThanks for your order {order.order_number} "
              f"({settings.CURRENCY_SYMBOL}{order.total}).\nTrack it any time: {settings.SITE_URL}/orders/{order.order_number}/\n",
              None, [user.email], fail_silently=True)
    return order


# ---- payments ---------------------------------------------------------------------
DECLINED_TEST_CARD = "4000000000000002"


def mock_charge(card_number):
    """Stand-in for a real gateway (Stripe/Razorpay/PayPal). Returns (ok, reference_or_error)."""
    digits = "".join(ch for ch in card_number if ch.isdigit())
    if len(digits) < 13 or len(digits) > 19:
        return False, "Enter a valid card number."
    if digits == DECLINED_TEST_CARD:
        return False, "Your card was declined (test card)."
    return True, "mock_" + digits[-4:] + "_" + timezone.now().strftime("%H%M%S")


def mark_paid(order, reference):
    order.payment_status = "paid"
    order.payment_ref = reference
    order.save(update_fields=["payment_status", "payment_ref"])
    notify(order.user, f"Payment received for {order.order_number}.", f"/orders/{order.order_number}/")


# ---- cancellations & refunds -----------------------------------------------------
def restock_item(item):
    if item.variant_id:
        item.variant.stock += item.quantity
        item.variant.save()
    elif item.product_id:
        item.product.stock += item.quantity
        item.product.save(update_fields=["stock"])


def refund_item(item):
    order = Order.objects.select_for_update().get(pk=item.order_id)  # fresh copy: avoids stale totals
    if order.payment_status in ("unpaid",):
        return
    order.refunded_amount += item.line_total
    live = order.items.exclude(status__in=("cancelled", "returned")).exclude(pk=item.pk).exists()
    order.payment_status = "partially_refunded" if live else "refunded"
    order.save(update_fields=["refunded_amount", "payment_status"])


@transaction.atomic
def cancel_item(item):
    if item.status not in ("pending", "processing"):
        raise OrderError("This item can no longer be cancelled.")
    restock_item(item)
    refund_item(item)
    item.status = "cancelled"
    item.save(update_fields=["status"])
    item.order.refresh_status()


@transaction.atomic
def cancel_order(order):
    if not order.can_cancel:
        raise OrderError("This order can no longer be cancelled.")
    for item in order.items.select_related("order", "product", "variant"):
        cancel_item(item)
    notify(order.user, f"Order {order.order_number} was cancelled.", f"/orders/{order.order_number}/")


@transaction.atomic
def resolve_return(ret, approve):
    if ret.status != "requested":
        raise OrderError("Already resolved.")
    if approve:
        item = ret.item
        restock_item(item)
        refund_item(item)
        item.status = "returned"
        item.save(update_fields=["status"])
        item.order.refresh_status()
        ret.status = "approved"
    else:
        ret.status = "rejected"
    ret.save(update_fields=["status"])
    notify(ret.user, f"Your return for {ret.item.name} was {'approved and refunded' if approve else 'rejected'}.",
           f"/orders/{ret.item.order.order_number}/")
