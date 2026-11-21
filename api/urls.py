from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health),
    path("categories/", views.categories),
    path("products/", views.products),
    path("products/<slug:slug>/", views.product_detail),
    path("suggest/", views.suggest),
    path("cart/", views.cart_get),
    path("cart/add/", views.cart_add),
    path("cart/update/", views.cart_update),
    path("cart/remove/", views.cart_remove),
    path("cart/clear/", views.cart_clear),
    path("cart/coupon/", views.cart_coupon),
    path("wishlist/", views.wishlist_list),
    path("wishlist/toggle/", views.wishlist_toggle),
    path("orders/", views.my_orders),
    path("notifications/", views.notifications),
    path("notifications/read/", views.notifications_read),
    path("vendor/stats/", views.vendor_stats),
]
