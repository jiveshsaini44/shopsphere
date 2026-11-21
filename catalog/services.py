"""Product search/filter logic shared by the HTML views and the JSON API."""
from decimal import Decimal, InvalidOperation

from django.db.models import F, Q

from .models import Category, Product

SORTS = {
    "newest": "-created",
    "price_asc": "price",
    "price_desc": "-price",
    "popular": "-views",
    "rating": "-avg_rating",
}


def _dec(value):
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return None


def filter_products(params, category=None, vendor=None):
    qs = Product.objects.active().select_related("category", "vendor")
    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q) | Q(vendor__store_name__icontains=q)
                       | Q(category__name__icontains=q))
    cat_slug = params.get("category")
    if category is None and cat_slug:
        category = Category.objects.filter(slug=cat_slug).first()
    if category is not None:
        qs = qs.filter(category_id__in=category.descendant_ids())
    if vendor is not None:
        qs = qs.filter(vendor=vendor)
    lo, hi = _dec(params.get("min_price")), _dec(params.get("max_price"))
    if lo is not None:
        qs = qs.filter(price__gte=lo)
    if hi is not None:
        qs = qs.filter(price__lte=hi)
    if params.get("in_stock") in ("1", "true", "on"):
        qs = qs.filter(stock__gt=0)
    min_rating = _dec(params.get("rating"))
    if min_rating is not None:
        qs = qs.filter(avg_rating__gte=float(min_rating))
    if params.get("on_sale") in ("1", "true", "on"):
        qs = qs.filter(compare_at_price__gt=F("price"))
    return qs.order_by(SORTS.get(params.get("sort"), "-created"), "-id")

