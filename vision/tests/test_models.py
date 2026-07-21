from django.core.exceptions import ValidationError
from django.test import TestCase

from vision.models import VideoFeed


class VideoFeedModelTests(TestCase):
    def test_rtsp_connection_is_valid(self):
        feed = VideoFeed(rtsp_url="rtsp://user:secret@camera.example:8554/live")

        feed.full_clean()
        feed.save()

        self.assertEqual(str(feed), f"Video Feed #{feed.pk}")
        self.assertEqual(feed.connection_host, "camera.example:8554")

    def test_non_rtsp_connection_is_rejected(self):
        feed = VideoFeed(rtsp_url="https://example.com/video.mp4")

        with self.assertRaises(ValidationError):
            feed.full_clean()
