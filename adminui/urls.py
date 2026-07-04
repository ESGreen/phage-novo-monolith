from django.urls import path

from . import views

app_name = "adminui"

urlpatterns = [
    path("admin/", views.home, name="home"),
    path("admin/users/", views.users, name="users"),
    path("admin/camp/", views.camp, name="camp"),
    path("admin/payments/", views.payments, name="payments"),
    path("admin/stripe/", views.stripe, name="stripe"),
    path("admin/pages/", views.pages, name="pages"),
    path("admin/menus/", views.menus, name="menus"),
    path("admin/media/", views.media, name="media"),
]
