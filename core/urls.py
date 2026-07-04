from django.urls import path

from . import views

urlpatterns = [
    path("", views.public_root_redirect, name="public-root-redirect"),
]
