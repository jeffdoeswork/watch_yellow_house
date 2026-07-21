from django.contrib import admin

from .models import VideoFeed


@admin.register(VideoFeed)
class VideoFeedAdmin(admin.ModelAdmin):
    fields = ("rtsp_url", "is_enabled")
    list_display = ("id", "connection_host", "is_enabled", "created_at")
    list_editable = ("is_enabled",)
    list_filter = ("is_enabled",)
    ordering = ("id",)

    @admin.display(description="Connection")
    def connection_host(self, feed):
        return feed.connection_host
