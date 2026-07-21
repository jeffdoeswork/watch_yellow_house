from urllib.parse import urlsplit

from django.core.validators import URLValidator
from django.db import models


class VideoFeed(models.Model):
    rtsp_url = models.TextField(
        "RTSP connection",
        validators=[URLValidator(schemes=("rtsp", "rtsps"))],
        help_text="Full RTSP URL, including credentials when required.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)

    def __str__(self):
        return f"Video Feed #{self.pk or 'new'}"

    @property
    def connection_host(self):
        parsed = urlsplit(self.rtsp_url)
        if not parsed.hostname:
            return "RTSP source"
        port = f":{parsed.port}" if parsed.port else ""
        return f"{parsed.hostname}{port}"
