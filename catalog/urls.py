from django.urls import path

from . import views

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("c/<slug:slug>/", views.product_list, name="category_detail"),
    path("p/<slug:slug>/", views.product_detail, name="product_detail"),
    path("p/<slug:slug>/review/", views.add_review, name="add_review"),
    path("wishlist/", views.wishlist, name="wishlist"),
]
