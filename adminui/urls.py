from django.urls import path

from . import views

app_name = "adminui"

urlpatterns = [
    path("admin/", views.home, name="home"),
    path("admin/users/", views.users, name="users"),
    path("admin/users/intro-email/", views.user_intro_email, name="user-intro-email"),
    path("admin/users/<int:user_id>/", views.user_edit, name="user-edit"),
    path("admin/camp/", views.camp, name="camp"),
    path("admin/camp/<int:year>/", views.camp_year_edit, name="camp-year-edit"),
    path("admin/payments/", views.payments, name="payments"),
    path("admin/stripe/", views.stripe, name="stripe"),
    path("admin/pages/", views.pages, name="pages"),
    path("admin/menus/", views.menus, name="menus"),
    path("admin/media/", views.media, name="media"),
]
