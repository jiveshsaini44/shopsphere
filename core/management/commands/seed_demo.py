"""python manage.py seed_demo  -> creates demo admin, vendors, customer, categories, products, coupons, reviews."""
import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from catalog.models import Category, Product, ProductVariant, Review
from orders.models import Coupon
from vendors.models import Vendor

CATALOG = {
    ("Electronics", "💻"): ["Wireless Earbuds", "Mechanical Keyboard", "4K Webcam", "Portable Charger 20000mAh", "Smart Watch", "Bluetooth Speaker"],
    ("Fashion", "👕"): ["Classic Cotton T-Shirt", "Slim Fit Jeans", "Running Sneakers", "Waterproof Jacket", "Leather Belt", "Wool Beanie"],
    ("Home & Kitchen", "🏠"): ["Ceramic Mug Set", "Cast Iron Skillet", "LED Desk Lamp", "Bamboo Cutting Board", "Aroma Diffuser", "Memory Foam Pillow"],
    ("Books", "📚"): ["Learn Python The Hard Way", "Design Patterns Handbook", "Mindful Productivity", "Cooking For Beginners", "Sci-Fi Anthology", "World Atlas"],
    ("Sports", "⚽"): ["Yoga Mat Pro", "Adjustable Dumbbells", "Insulated Water Bottle", "Resistance Bands", "Trail Backpack 30L", "Jump Rope"],
}
SIZES = ["S", "M", "L", "XL"]


class Command(BaseCommand):
    help = "Create demo data (safe to run more than once)."

    def handle(self, *args, **opts):
        random.seed(7)
        User = get_user_model()
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@example.com", "admin12345")
        customer, _ = User.objects.get_or_create(username="customer", defaults={"email": "customer@example.com", "first_name": "Casey"})
        customer.set_password("demo12345"); customer.save()

        vendors = []
        for i, (store, desc) in enumerate([("TechNest", "Gadgets and gear."), ("Urban Threads", "Everyday fashion."), ("Home & Hearth", "Cozy living essentials.")], 1):
            u, _ = User.objects.get_or_create(username=f"vendor{i}", defaults={"email": f"vendor{i}@example.com", "first_name": store.split()[0]})
            u.set_password("demo12345"); u.save()
            v, _ = Vendor.objects.get_or_create(user=u, defaults={"store_name": store, "description": desc})
            v.status = "approved"; v.save()
            vendors.append(v)

        n = 0
        for (cat_name, icon), names in CATALOG.items():
            cat, _ = Category.objects.get_or_create(name=cat_name, defaults={"icon": icon})
            for name in names:
                if Product.objects.filter(name=name).exists():
                    continue
                price = Decimal(random.choice(["9.99", "14.50", "19.99", "24.00", "39.90", "59.00", "89.99", "129.00"]))
                p = Product.objects.create(
                    vendor=random.choice(vendors), category=cat, name=name, price=price,
                    compare_at_price=(price * Decimal("1.25")).quantize(Decimal("0.01")) if random.random() < .4 else None,
                    stock=random.randint(0, 40), sku=f"SKU{random.randint(10000, 99999)}", featured=random.random() < .25,
                    description=f"{name} – a customer favourite. Built to last, easy to use, and backed by our seller guarantee.\n\nFeatures:\n• Premium materials\n• 1-year warranty\n• Fast dispatch")
                if cat_name == "Fashion":
                    for s in SIZES:
                        ProductVariant.objects.create(product=p, name=f"Size {s}", price_delta=0, stock=random.randint(0, 10))
                for u in random.sample([customer], 1):
                    if random.random() < .7:
                        Review.objects.create(product=p, user=u, rating=random.randint(3, 5), title="Great", body="Really happy with this purchase.", verified_purchase=True)
                n += 1

        Coupon.objects.get_or_create(code="WELCOME10", defaults={"discount_type": "percent", "value": 10})
        Coupon.objects.get_or_create(code="SAVE5", defaults={"discount_type": "fixed", "value": 5, "min_order": 30})
        self.stdout.write(self.style.SUCCESS(f"Seeded {n} products."))
        self.stdout.write("Admin: admin / admin12345 | Vendors: vendor1..3 / demo12345 | Customer: customer / demo12345")
        self.stdout.write("Coupons: WELCOME10 (10%), SAVE5 ($5 off $30+)")
