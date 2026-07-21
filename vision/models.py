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


class FeedDetectionState(models.Model):
    """Latest bounded detection state published by the YOLO worker."""

    feed = models.OneToOneField(
        VideoFeed,
        on_delete=models.CASCADE,
        related_name="detection_state",
    )
    count_history = models.JSONField(default=list, blank=True)
    stable_counts = models.JSONField(default=dict, blank=True)
    current_counts = models.JSONField(default=dict, blank=True)
    boxes = models.JSONField(default=list, blank=True)
    frame_number = models.PositiveBigIntegerField(default=0)
    inference_ms = models.FloatField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "feed detection state"
        verbose_name_plural = "feed detection states"

    def __str__(self):
        return f"Detections for {self.feed}"
