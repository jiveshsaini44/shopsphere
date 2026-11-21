from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.cache import cache_control

from catalog.models import Category, Product

PAGES = {
    "about": ("About us", "ShopSphere is a multi-vendor marketplace where independent sellers open their own stores and customers shop them all in a single cart."),
    "privacy": ("Privacy policy", "We collect only the data needed to process your orders (name, email, address, phone). We never sell personal data. You can request export or deletion of your account at any time by contacting support."),
    "terms": ("Terms of service", "By using ShopSphere you agree to buy and sell lawfully. Vendors are responsible for their listings, fulfilment and customer service. The marketplace charges a commission on each completed sale."),
    "shipping-returns": ("Shipping & returns", "Orders over the free-shipping threshold ship free. Items can be returned within the return window after delivery. Refunds are issued to the original payment method once the vendor approves the return."),
    "contact": ("Contact", "Questions? Email support@shopsphere.local. We reply within one business day."),
}


def home(request):
    qs = Product.objects.active().select_related("category", "vendor")
    recent_ids = request.session.get("recent", [])
    recent = {p.pk: p for p in qs.filter(pk__in=recent_ids)}
    ctx = {
        "categories": Category.objects.filter(parent__isnull=True),
        "featured": qs.filter(featured=True)[:8],
        "new_arrivals": qs.order_by("-created")[:8],
        "top_rated": qs.filter(review_count__gt=0).order_by("-avg_rating", "-review_count")[:8],
        "recent": [recent[i] for i in recent_ids if i in recent][:8],
    }
    return render(request, "core/home.html", ctx)


def static_page(request, slug):
    title, body = PAGES[slug]
    return render(request, "core/page.html", {"title": title, "body": body})


def offline(request):
    return render(request, "core/offline.html")


def robots(request):
    lines = ["User-agent: *", "Disallow: /admin/", "Disallow: /api/", "Disallow: /checkout/",
             "Disallow: /cart/", "Disallow: /accounts/", "Disallow: /vendor/", f"Sitemap: {settings.SITE_URL}/sitemap.xml"]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def manifest(request):
    data = {
        "name": settings.SHOP_NAME, "short_name": settings.SHOP_NAME, "start_url": "/",
        "display": "standalone", "background_color": "#ffffff", "theme_color": "#4f46e5",
        "description": "Multi-vendor marketplace",
        "icons": [
            {"src": static("img/icon-192.png"), "sizes": "192x192", "type": "image/png"},
            {"src": static("img/icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
    }
    return JsonResponse(data, content_type="application/manifest+json")


@cache_control(max_age=0, no_cache=True)
def service_worker(request):
    js = (Path(settings.BASE_DIR) / "static" / "js" / "sw.js").read_text(encoding="utf-8")
    resp = HttpResponse(js, content_type="application/javascript")
    resp["Service-Worker-Allowed"] = "/"
    return resp


def healthz(request):
    return JsonResponse({"status": "ok"})


def error_404(request, exception=None):
    return render(request, "core/404.html", status=404)


def error_500(request):
    return render(request, "core/500.html", status=500)
