from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .models import Cart, CartItem


@receiver(user_logged_in)
def merge_guest_cart(sender, request, user, **kwargs):
    """When a guest logs in, fold their anonymous cart into their saved cart."""
    if request is None:
        return
    cart_id = request.session.get("cart_id")
    if not cart_id:
        return
    guest = Cart.objects.filter(pk=cart_id, user__isnull=True).first()
    if not guest:
        return
    mine, _ = Cart.objects.get_or_create(user=user)
    for it in guest.items.all():
        obj, created = CartItem.objects.get_or_create(
            cart=mine, product=it.product, variant=it.variant, defaults={"quantity": it.quantity})
        if not created:
            obj.quantity += it.quantity
            obj.save()
    guest.delete()
    request.session.pop("cart_id", None)
