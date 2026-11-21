from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Category, Product
from vendors.models import Vendor

from . import services
from .models import Cart, CartItem, Coupon

ADDR = {"full_name": "A B", "phone": "123", "line1": "1 Main", "city": "X", "postal_code": "1", "country": "US"}


class MarketplaceFlowTests(TestCase):
    def setUp(self):
        self.v_user = User.objects.create_user("seller", "s@x.com", "pw12345678")
        self.vendor = Vendor.objects.create(user=self.v_user, store_name="Shop One", status="approved")
        self.cat = Category.objects.create(name="Misc")
        self.p = Product.objects.create(vendor=self.vendor, category=self.cat, name="Widget", price=Decimal("100.00"), stock=5, description="d")
        self.buyer = User.objects.create_user("buyer", "b@x.com", "pw12345678")

    def _cart(self, qty=2):
        cart = Cart.objects.create(user=self.buyer)
        CartItem.objects.create(cart=cart, product=self.p, quantity=qty)
        return cart

    def test_totals_free_shipping_and_tax(self):
        t = services.cart_totals(self._cart(2))
        self.assertEqual(t["subtotal"], Decimal("200.00"))
        self.assertEqual(t["shipping"], Decimal("0.00"))
        self.assertEqual(t["tax"], Decimal("16.00"))

    def test_coupon_percent(self):
        Coupon.objects.create(code="TEN", discount_type="percent", value=10)
        t = services.cart_totals(self._cart(1), "ten")
        self.assertEqual(t["discount"], Decimal("10.00"))

    def test_place_order_splits_commission_and_reduces_stock(self):
        order = services.place_order(self.buyer, self._cart(2), ADDR, "cod")
        item = order.items.get()
        self.assertEqual(item.vendor_earning, Decimal("180.00"))  # 10% default commission
        self.p.refresh_from_db()
        self.assertEqual(self.p.stock, 3)

    def test_cannot_oversell(self):
        with self.assertRaises(services.OrderError):
            services.place_order(self.buyer, self._cart(9), ADDR, "cod")

    def test_cancel_restocks(self):
        order = services.place_order(self.buyer, self._cart(2), ADDR, "cod")
        services.cancel_order(order)
        self.p.refresh_from_db()
        self.assertEqual(self.p.stock, 5)

    def test_api_cart_add_and_public_pages(self):
        r = self.client.post("/api/cart/add/", {"product_id": self.p.pk, "quantity": 1}, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 1)
        for name in ("home", "product_list", "cart"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertEqual(self.client.get(self.p.get_absolute_url()).status_code, 200)
