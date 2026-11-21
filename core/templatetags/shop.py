from decimal import Decimal, InvalidOperation

from django import template
from django.conf import settings

register = template.Library()


@register.filter
def money(value):
    try:
        value = Decimal(value)
    except (InvalidOperation, TypeError):
        value = Decimal("0")
    return f"{settings.CURRENCY_SYMBOL}{value:,.2f}"


@register.filter
def rating_pct(value):
    try:
        return "%d" % round(float(value) / 5 * 100)
    except (TypeError, ValueError):
        return "0"


@register.filter
def get_item(d, key):
    return d.get(key) if hasattr(d, "get") else None
