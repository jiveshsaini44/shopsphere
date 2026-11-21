from django.conf import settings


def shop(request):
    from catalog.models import Category
    from orders.services import get_cart

    ctx = {
        "SHOP_NAME": settings.SHOP_NAME,
        "CURRENCY": settings.CURRENCY_SYMBOL,
        "CURRENCY_CODE": settings.CURRENCY_CODE,
        "FREE_SHIPPING": settings.FREE_SHIPPING_THRESHOLD,
        "nav_categories": Category.objects.filter(parent__isnull=True)[:8],
        "cart_count": 0,
        "unread_count": 0,
        "wished_ids": set(),
    }
    cart = get_cart(request, create=False)
    if cart:
        ctx["cart_count"] = sum(i.quantity for i in cart.items.all())
    if request.user.is_authenticated:
        ctx["wished_ids"] = set(request.user.wishlist.values_list("product_id", flat=True))
        ctx["unread_count"] = request.user.notifications.filter(is_read=False).count()
    return ctx
