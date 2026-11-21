from django.urls import path

from . import views

urlpatterns = [
    path("apply/", views.apply, name="vendor_apply"),
    path("", views.dashboard, name="vendor_dashboard"),
    path("products/", views.product_list, name="vendor_products"),
    path("products/new/", views.product_create, name="vendor_product_new"),
    path("products/<int:pk>/edit/", views.product_edit, name="vendor_product_edit"),
    path("products/<int:pk>/delete/", views.product_delete, name="vendor_product_delete"),
    path("products/<int:pk>/variants/add/", views.variant_add, name="vendor_variant_add"),
    path("variants/<int:pk>/delete/", views.variant_delete, name="vendor_variant_delete"),
    path("products/<int:pk>/images/add/", views.image_add, name="vendor_image_add"),
    path("images/<int:pk>/delete/", views.image_delete, name="vendor_image_delete"),
    path("orders/", views.orders, name="vendor_orders"),
    path("orders/item/<int:pk>/update/", views.order_item_update, name="vendor_item_update"),
    path("returns/", views.returns, name="vendor_returns"),
    path("returns/<int:pk>/resolve/", views.return_resolve, name="vendor_return_resolve"),
    path("payouts/", views.payouts, name="vendor_payouts"),
    path("payouts/request/", views.payout_request, name="vendor_payout_request"),
    path("settings/", views.store_settings, name="vendor_settings"),
]
