from django.urls import path

from . import views

app_name = "surveys"

urlpatterns = [
    path("survey/<slug:slug>/complete/", views.survey_complete, name="survey-complete"),
    path("survey/<slug:slug>/", views.survey_detail, name="survey-detail"),
]
