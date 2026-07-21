from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("detections/summary/", views.dashboard_detections, name="detections"),
]
