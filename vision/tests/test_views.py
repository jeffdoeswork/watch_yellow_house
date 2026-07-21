from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from vision.models import VideoFeed


class VideoFeedViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="viewer",
            password="test-password",
        )
        self.feed = VideoFeed.objects.create(
            rtsp_url="rtsp://camera-user:secret@camera.example:8554/live"
        )

    def test_list_requires_login(self):
        response = self.client.get(reverse("vision:video_feed_list"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_authenticated_list_contains_saved_feed(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("vision:video_feed_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Video Feed #{self.feed.pk}")
        self.assertContains(response, "camera.example:8554")
        self.assertNotContains(response, "camera-user:secret")

    def test_detail_does_not_expose_connection_string(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("vision:video_feed_detail", args=(self.feed.pk,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Live video feed")
        self.assertNotContains(response, self.feed.rtsp_url)

    @patch("vision.views.iter_mjpeg_frames")
    @patch("vision.views.open_rtsp_capture")
    def test_stream_uses_server_side_rtsp_connection(self, open_capture, frames):
        self.client.force_login(self.user)
        capture = MagicMock()
        capture.isOpened.return_value = True
        open_capture.return_value = capture
        frames.return_value = iter((b"frame-data",))

        response = self.client.get(
            reverse("vision:video_feed_stream", args=(self.feed.pk,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"frame-data")
        open_capture.assert_called_once_with(self.feed.rtsp_url)
