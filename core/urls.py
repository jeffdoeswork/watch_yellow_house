from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("briefing/", views.briefing, name="briefing"),
    path("timeline/", views.timeline, name="timeline"),
    path("sources/", views.sources, name="sources"),
]

