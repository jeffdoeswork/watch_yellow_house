from django.contrib import admin

from .models import VideoFeed


@admin.register(VideoFeed)
class VideoFeedAdmin(admin.ModelAdmin):
    fields = ("rtsp_url",)
    list_display = ("id", "connection_host", "created_at")
    ordering = ("id",)

    @admin.display(description="Connection")
    def connection_host(self, feed):
        return feed.connection_host
