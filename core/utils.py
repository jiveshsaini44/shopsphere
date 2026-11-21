from django.core.cache import cache
from django.utils.text import slugify


def client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "")


def rate_limited(request, scope, limit=10, window=900):
    """Tiny cache-based rate limiter. Returns True when the caller exceeded `limit` hits per `window` secs."""
    key = f"rl:{scope}:{client_ip(request)}"
    cache.add(key, 0, window)
    try:
        n = cache.incr(key)
    except ValueError:
        cache.set(key, 1, window)
        n = 1
    return n > limit


def unique_slug(model, value, instance=None, field="slug"):
    base = slugify(value)[:200] or "item"
    slug, n = base, 2
    qs = model.objects.all()
    if instance is not None and instance.pk:
        qs = qs.exclude(pk=instance.pk)
    while qs.filter(**{field: slug}).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug
