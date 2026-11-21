from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ReviewForm
from .models import Category, Product, Wishlist
from .services import filter_products


def product_list(request, slug=None):
    category = get_object_or_404(Category, slug=slug) if slug else None
    qs = filter_products(request.GET, category=category)
    page = Paginator(qs, settings.PAGE_SIZE).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    ctx = {
        "page": page, "category": category, "q": request.GET.get("q", ""),
        "sort": request.GET.get("sort", "newest"), "querystring": params.urlencode(),
        "categories": Category.objects.filter(parent__isnull=True).prefetch_related("children"),
        "f": request.GET,
    }
    return render(request, "catalog/product_list.html", ctx)


def product_detail(request, slug):
    product = get_object_or_404(Product.objects.active().select_related("vendor", "category"), slug=slug)
    Product.objects.filter(pk=product.pk).update(views=F("views") + 1)

    recent = [i for i in request.session.get("recent", []) if i != product.pk]
    request.session["recent"] = ([product.pk] + recent)[:10]

    related = (Product.objects.active().filter(category=product.category).exclude(pk=product.pk)[:4]
               if product.category else [])
    in_wishlist = request.user.is_authenticated and Wishlist.objects.filter(user=request.user, product=product).exists()
    my_review = product.reviews.filter(user=request.user).first() if request.user.is_authenticated else None
    ctx = {
        "product": product, "variants": product.variants.all(), "gallery": product.images.all(),
        "reviews": product.reviews.select_related("user")[:30], "related": related,
        "in_wishlist": in_wishlist, "review_form": ReviewForm(instance=my_review), "my_review": my_review,
    }
    return render(request, "catalog/product_detail.html", ctx)


@login_required
@require_POST
def add_review(request, slug):
    from orders.models import OrderItem

    product = get_object_or_404(Product, slug=slug)
    existing = product.reviews.filter(user=request.user).first()
    form = ReviewForm(request.POST, instance=existing)
    if form.is_valid():
        review = form.save(commit=False)
        review.product, review.user = product, request.user
        review.verified_purchase = OrderItem.objects.filter(
            order__user=request.user, product=product, status="delivered").exists()
        review.save()
        messages.success(request, "Thanks for your review!")
    else:
        messages.error(request, "Please select a rating between 1 and 5.")
    return redirect(product)


@login_required
def wishlist(request):
    items = Wishlist.objects.filter(user=request.user, product__is_active=True).select_related(
        "product", "product__category", "product__vendor")
    return render(request, "catalog/wishlist.html", {"items": items})
