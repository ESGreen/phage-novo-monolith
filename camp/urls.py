from django.urls import path

from . import views

app_name = "camp"

urlpatterns = [
    path("dashboard/", views.dashboard_redirect, name="dashboard-current"),
    path("phagebook/", views.phagebook_redirect, name="phagebook-current"),
    path("<int:year>/dashboard/", views.dashboard, name="dashboard"),
    path("<int:year>/phagebook/", views.phagebook, name="phagebook"),
    path("<int:year>/taxes/return/", views.taxes_return, name="taxes-return"),
    path("<int:year>/taxes/", views.taxes, name="taxes"),
    path("<int:year>/", views.year_redirect, name="year-root"),
]
