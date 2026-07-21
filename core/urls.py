from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("video-feeds/", views.video_feeds, name="video_feeds"),
]
