from django.urls import path

from . import views

app_name = "content"

urlpatterns = [
    path("derived-media/<path:file_path>", views.derived_media, name="derived-media"),
    path("menu/<slug:menu_name>/", views.menu_detail, name="menu-detail"),
    path("pages/<slug:slug>/", views.page_detail, name="page-detail"),
]
