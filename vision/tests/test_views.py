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
        self.assertContains(response, "<video controls")
        self.assertContains(response, 'type="video/mp4"')
        self.assertNotContains(response, self.feed.rtsp_url)

    @patch("vision.views.iter_video_chunks")
    @patch("vision.views.open_browser_video_stream")
    def test_stream_uses_server_side_rtsp_connection(self, open_stream, chunks):
        self.client.force_login(self.user)
        process = MagicMock()
        open_stream.return_value = process
        chunks.return_value = iter((b"video-data",))

        response = self.client.get(
            reverse("vision:video_feed_stream", args=(self.feed.pk,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "video/mp4")
        self.assertEqual(b"".join(response.streaming_content), b"video-data")
        open_stream.assert_called_once_with(self.feed.rtsp_url)
        chunks.assert_called_once_with(process)

    @patch("vision.views.open_browser_video_stream", side_effect=FileNotFoundError)
    def test_stream_returns_service_unavailable_without_ffmpeg(self, open_stream):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("vision:video_feed_stream", args=(self.feed.pk,))
        )

        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, self.feed.rtsp_url, status_code=503)
