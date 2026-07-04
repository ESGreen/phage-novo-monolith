"""Top-level URL routing for The Phage website."""

from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [
    path("", include("accounts.urls")),
    path("", include("adminui.urls")),
    path("", include("camp.urls")),
    path("", include("content.urls")),
    path("", include("core.urls")),
    path("", include("payments.urls")),
]

if settings.DEBUG:
    urlpatterns += static("/public/", document_root=settings.PUBLIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
