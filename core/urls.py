from django.contrib.sitemaps.views import sitemap
from django.urls import path

from . import views
from .sitemaps import sitemaps

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.static_page, {"slug": "about"}, name="page_about"),
    path("privacy/", views.static_page, {"slug": "privacy"}, name="page_privacy"),
    path("terms/", views.static_page, {"slug": "terms"}, name="page_terms"),
    path("shipping-returns/", views.static_page, {"slug": "shipping-returns"}, name="page_shipping"),
    path("contact/", views.static_page, {"slug": "contact"}, name="page_contact"),
    path("offline/", views.offline, name="offline"),
    path("robots.txt", views.robots, name="robots"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="sw"),
    path("healthz/", views.healthz, name="healthz"),
]
