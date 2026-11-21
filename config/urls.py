from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from vendors.views import storefront

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("accounts/", include("accounts.urls")),
    path("vendor/", include("vendors.urls")),
    path("store/<slug:slug>/", storefront, name="storefront"),
    path("shop/", include("catalog.urls")),
    path("", include("orders.urls")),
    path("api/", include("api.urls")),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "core.views.error_404"
handler500 = "core.views.error_500"
