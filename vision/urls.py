from django.urls import path

from . import views

app_name = "vision"

urlpatterns = [
    path("video-feeds/", views.video_feed_list, name="video_feed_list"),
    path("video-feeds/<int:pk>/", views.video_feed_detail, name="video_feed_detail"),
    path(
        "video-feeds/<int:pk>/stream/",
        views.video_feed_stream,
        name="video_feed_stream",
    ),
]
