"""JSON API used by the storefront JavaScript (session + CSRF authenticated)."""
import json
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import F, Sum, DecimalField
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from catalog.models import Category, Product, ProductVariant, Wishlist
from catalog.services import filter_products
from orders import services
from orders.models import CartItem


def api_login_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        return view(request, *args, **kwargs)
    return wrapper


def body(request):
    try:
        data = json.loads(request.body or "{}")
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


def err(message, status=400):
    return JsonResponse({"error": message}, status=status)


def product_dict(p, detail=False):
    d = {
        "id": p.pk, "name": p.name, "slug": p.slug, "url": p.get_absolute_url(),
        "price": str(p.price), "compare_at_price": str(p.compare_at_price) if p.compare_at_price else None,
        "discount_percent": p.discount_percent, "image": p.image.url if p.image else None,
        "rating": p.avg_rating, "review_count": p.review_count, "in_stock": p.in_stock, "stock": p.stock,
        "vendor": {"name": p.vendor.store_name, "slug": p.vendor.slug},
        "category": p.category.name if p.category else None,
    }
    if detail:
        d["description"] = p.description
        d["variants"] = [{"id": v.pk, "name": v.name, "price": str(v.price), "stock": v.stock} for v in p.variants.all()]
        d["images"] = [i.image.url for i in p.images.all()]
    return d


# ---- catalog ------------------------------------------------------------------
@require_GET
def categories(request):
    data = [{"id": c.pk, "name": c.name, "slug": c.slug, "icon": c.icon,
             "parent": c.parent.slug if c.parent else None} for c in Category.objects.select_related("parent")]
    return JsonResponse({"categories": data})


@require_GET
def products(request):
    qs = filter_products(request.GET)
    try:
        size = max(1, min(int(request.GET.get("page_size", settings.PAGE_SIZE)), 60))
    except ValueError:
        size = settings.PAGE_SIZE
    page = Paginator(qs, size).get_page(request.GET.get("page"))
    return JsonResponse({"count": page.paginator.count, "page": page.number, "pages": page.paginator.num_pages,
                         "results": [product_dict(p) for p in page]})


@require_GET
def product_detail(request, slug):
    p = Product.objects.active().select_related("vendor", "category").filter(slug=slug).first()
    if not p:
        return err("Product not found", 404)
    return JsonResponse(product_dict(p, detail=True))


@require_GET
def suggest(request):
    term = request.GET.get("q", "").strip()
    if len(term) < 2:
        return JsonResponse({"results": []})
    qs = Product.objects.active().filter(name__icontains=term).select_related("category")[:6]
    return JsonResponse({"results": [{"name": p.name, "url": p.get_absolute_url(), "price": str(p.price),
                                      "image": p.image.url if p.image else None,
                                      "icon": p.category.icon if p.category else "🛍️"} for p in qs]})


# ---- cart ---------------------------------------------------------------------
def cart_payload(request):
    cart = services.get_cart(request, create=False)
    t = services.cart_totals(cart, request.session.get("coupon", ""))
    items = []
    for i in t["items"]:
        items.append({
            "id": i.pk, "product_id": i.product_id, "name": i.product.name, "url": i.product.get_absolute_url(),
            "variant": i.variant.name if i.variant else "", "unit_price": str(i.unit_price), "quantity": i.quantity,
            "line_total": str(i.line_total), "stock": i.available, "vendor": i.product.vendor.store_name,
            "image": i.product.image.url if i.product.image else None,
            "icon": i.product.category.icon if i.product.category else "🛍️",
        })
    free_from = float(settings.FREE_SHIPPING_THRESHOLD)
    return {
        "items": items, "count": t["count"], "subtotal": str(t["subtotal"]), "discount": str(t["discount"]),
        "shipping": str(t["shipping"]), "tax": str(t["tax"]), "total": str(t["total"]),
        "coupon": t["coupon"].code if t["coupon"] else None, "coupon_message": t["coupon_message"],
        "free_shipping_threshold": free_from,
        "free_shipping_remaining": max(0, round(free_from - float(t["subtotal"] - t["discount"]), 2)),
    }


@require_GET
def cart_get(request):
    return JsonResponse(cart_payload(request))


@require_POST
def cart_add(request):
    data = body(request)
    try:
        product = Product.objects.active().filter(pk=int(data.get("product_id"))).first()
    except (TypeError, ValueError):
        product = None
    if not product:
        return err("Product not found", 404)
    try:
        qty = max(1, int(data.get("quantity", 1)))
    except (TypeError, ValueError):
        return err("Invalid quantity")
    variant = None
    if product.variants.exists():
        variant = ProductVariant.objects.filter(pk=data.get("variant_id"), product=product).first()
        if not variant:
            return err("Please choose an option (size/colour) first.")
    available = variant.stock if variant else product.stock
    cart = services.get_cart(request)
    item = CartItem.objects.filter(cart=cart, product=product, variant=variant).first()
    new_qty = (item.quantity if item else 0) + qty
    if new_qty > available:
        return err(f"Only {available} in stock." if available else "Out of stock.")
    if item:
        item.quantity = new_qty
        item.save()
    else:
        CartItem.objects.create(cart=cart, product=product, variant=variant, quantity=new_qty)
    return JsonResponse(cart_payload(request))


@require_POST
def cart_update(request):
    data = body(request)
    cart = services.get_cart(request)
    item = CartItem.objects.filter(cart=cart, pk=data.get("item_id")).select_related("product", "variant").first()
    if not item:
        return err("Item not found", 404)
    try:
        qty = int(data.get("quantity", 1))
    except (TypeError, ValueError):
        return err("Invalid quantity")
    if qty <= 0:
        item.delete()
    elif qty > item.available:
        return err(f"Only {item.available} in stock.")
    else:
        item.quantity = qty
        item.save()
    return JsonResponse(cart_payload(request))


@require_POST
def cart_remove(request):
    cart = services.get_cart(request)
    CartItem.objects.filter(cart=cart, pk=body(request).get("item_id")).delete()
    return JsonResponse(cart_payload(request))


@require_POST
def cart_clear(request):
    services.get_cart(request).items.all().delete()
    request.session.pop("coupon", None)
    return JsonResponse(cart_payload(request))


@require_POST
def cart_coupon(request):
    code = (body(request).get("code") or "").strip()
    if not code:
        request.session.pop("coupon", None)
        return JsonResponse(cart_payload(request))
    cart = services.get_cart(request)
    t = services.cart_totals(cart, code)
    if not t["coupon"]:
        return err(t["coupon_message"] or "Invalid coupon")
    request.session["coupon"] = t["coupon"].code
    return JsonResponse(cart_payload(request))


# ---- wishlist -------------------------------------------------------------------
@require_POST
@api_login_required
def wishlist_toggle(request):
    product = Product.objects.active().filter(pk=body(request).get("product_id")).first()
    if not product:
        return err("Product not found", 404)
    obj, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    if not created:
        obj.delete()
    return JsonResponse({"wishlisted": created, "count": Wishlist.objects.filter(user=request.user).count()})


@require_GET
@api_login_required
def wishlist_list(request):
    qs = Wishlist.objects.filter(user=request.user).select_related("product", "product__vendor", "product__category")
    return JsonResponse({"results": [product_dict(w.product) for w in qs]})


# ---- orders / notifications -------------------------------------------------------
@require_GET
@api_login_required
def my_orders(request):
    data = [{
        "order_number": o.order_number, "status": o.status, "payment_status": o.payment_status,
        "total": str(o.total), "created": o.created.isoformat(),
        "items": [{"name": i.name, "quantity": i.quantity, "status": i.status, "tracking": i.tracking_number}
                  for i in o.items.all()],
    } for o in request.user.orders.prefetch_related("items")[:50]]
    return JsonResponse({"orders": data})


@require_GET
@api_login_required
def notifications(request):
    qs = request.user.notifications.all()[:20]
    return JsonResponse({"unread": request.user.notifications.filter(is_read=False).count(),
                         "results": [{"id": n.pk, "message": n.message, "link": n.link, "is_read": n.is_read,
                                      "created": n.created.isoformat()} for n in qs]})


@require_POST
@api_login_required
def notifications_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return JsonResponse({"unread": 0})


# ---- vendor analytics ---------------------------------------------------------------
@require_GET
@api_login_required
def vendor_stats(request):
    vendor = getattr(request.user, "vendor", None)
    if vendor is None or vendor.status != "approved":
        return err("Vendor access only", 403)
    since = timezone.now() - timedelta(days=29)
    rows = (vendor.order_items.filter(order__created__gte=since).exclude(status__in=["cancelled", "returned"])
            .annotate(day=TruncDate("order__created")).values("day")
            .annotate(revenue=Sum(F("price") * F("quantity"), output_field=DecimalField(max_digits=12, decimal_places=2)))
            .order_by("day"))
    by_day = {r["day"].isoformat(): float(r["revenue"]) for r in rows}
    days = [(since + timedelta(days=i)).date().isoformat() for i in range(30)]
    return JsonResponse({"labels": days, "revenue": [by_day.get(d, 0) for d in days],
                         "balance": str(vendor.balance), "earned": str(vendor.earned)})


@require_GET
def health(request):
    return JsonResponse({"status": "ok", "time": timezone.now().isoformat()})
