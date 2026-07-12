from django.urls import path

from . import views

app_name = "adminui"

urlpatterns = [
    path("admin/", views.home, name="home"),
    path("admin/users/", views.users, name="users"),
    path("admin/users/intro-email/", views.user_intro_email, name="user-intro-email"),
    path("admin/users/<int:user_id>/", views.user_edit, name="user-edit"),
    path("admin/camp/", views.camp, name="camp"),
    path(
        "admin/camp/<int:year>/tax-tier/<int:tier_id>/",
        views.camp_tax_tier_edit,
        name="camp-tax-tier-edit",
    ),
    path(
        "admin/camp/<int:year>/tax-add-on/<int:add_on_id>/",
        views.camp_tax_add_on_edit,
        name="camp-tax-add-on-edit",
    ),
    path("admin/camp/<int:year>/", views.camp_year_edit, name="camp-year-edit"),
    path("admin/payments/", views.payments, name="payments"),
    path("admin/payments/add/", views.payment_add, name="payment-add"),
    path("admin/stripe/", views.stripe, name="stripe"),
    path("admin/pages/", views.pages, name="pages"),
    path("admin/pages/<slug:slug>/", views.page_edit, name="page-edit"),
    path("admin/surveys/", views.surveys, name="surveys"),
    path("admin/surveys/<slug:slug>/responses/", views.survey_responses, name="survey-responses"),
    path("admin/surveys/<slug:slug>/responses.csv", views.survey_export, name="survey-export"),
    path(
        "admin/surveys/<slug:slug>/<int:question_id>/",
        views.survey_question_edit,
        name="survey-question-edit",
    ),
    path("admin/surveys/<slug:slug>/", views.survey_edit, name="survey-edit"),
    path("admin/menus/", views.menus, name="menus"),
    path("admin/menus/<slug:menu_name>/", views.menu_edit, name="menu-edit"),
    path("admin/menu-items/<int:item_id>/", views.menu_item_edit, name="menu-item-edit"),
    path("admin/media/", views.media, name="media"),
]
