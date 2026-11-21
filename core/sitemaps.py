from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from catalog.models import Category, Product
from vendors.models import Vendor


class StaticSitemap(Sitemap):
    priority = 0.5

    def items(self):
        return ["home", "product_list", "page_about", "page_shipping", "page_contact"]

    def location(self, name):
        return reverse(name)


class ProductSitemap(Sitemap):
    priority = 0.8

    def items(self):
        return Product.objects.active()

    def lastmod(self, obj):
        return obj.updated


class CategorySitemap(Sitemap):
    priority = 0.6

    def items(self):
        return Category.objects.all()


class StoreSitemap(Sitemap):
    priority = 0.4

    def items(self):
        return Vendor.objects.filter(status="approved")


sitemaps = {"static": StaticSitemap, "products": ProductSitemap, "categories": CategorySitemap, "stores": StoreSitemap}
