from django.urls import path

from . import views

urlpatterns = [
    path("cart/", views.cart_page, name="cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("pay/<str:number>/", views.mock_pay, name="mock_pay"),
    path("payments/webhook/", views.payment_webhook, name="payment_webhook"),
    path("orders/", views.order_list, name="order_list"),
    path("orders/<str:number>/", views.order_detail, name="order_detail"),
    path("orders/<str:number>/invoice/", views.invoice, name="invoice"),
    path("orders/<str:number>/cancel/", views.order_cancel, name="order_cancel"),
    path("orders/item/<int:item_id>/return/", views.return_request, name="return_request"),
]
