from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from vision.models import FeedDetectionState, VideoFeed


class VideoFeedViewTests(TestCase):
    def setUp(self):
        self.preview_directory = TemporaryDirectory()
        self.preview_settings = override_settings(
            YOLO_PREVIEW_ROOT=Path(self.preview_directory.name)
        )
        self.preview_settings.enable()
        self.addCleanup(self.preview_settings.disable)
        self.addCleanup(self.preview_directory.cleanup)
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
        self.assertContains(response, "detection-overlay")
        self.assertContains(response, 'data-quality-mode="low" aria-pressed="true"')
        self.assertContains(response, "Annotated 1 FPS preview · no audio")
        self.assertContains(
            response,
            f'data-preview-url="{reverse("vision:video_feed_preview", args=(self.feed.pk,))}"',
        )
        self.assertContains(
            response,
            f'data-stream-url="{reverse("vision:video_feed_stream", args=(self.feed.pk,))}"',
        )
        self.assertContains(response, "data-high-quality-video hidden")
        self.assertContains(response, "data-fullscreen-button")
        self.assertContains(response, 'aria-label="Enter fullscreen"')
        self.assertNotContains(response, "<source")
        self.assertNotContains(response, self.feed.rtsp_url)

    def test_detection_endpoint_requires_login(self):
        response = self.client.get(
            reverse("vision:video_feed_detections", args=(self.feed.pk,))
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_detection_endpoint_returns_feed_state(self):
        FeedDetectionState.objects.create(
            feed=self.feed,
            stable_counts={"person": 2},
            current_counts={"person": 3},
            boxes=[{"class_name": "person", "confidence": 0.9}],
            frame_number=12,
            inference_ms=15.2,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("vision:video_feed_detections", args=(self.feed.pk,))
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["stable_counts"], {"person": 2})
        self.assertEqual(payload["current_counts"], {"person": 3})
        self.assertEqual(payload["frame_number"], 12)
        self.assertEqual(payload["inference_ms"], 15.2)
        self.assertEqual(payload["target_fps"], 2)
        self.assertTrue(payload["is_active"])
        self.assertEqual(payload["status"], "detecting")
        self.assertNotContains(response, self.feed.rtsp_url)

    def test_detail_shows_simple_configured_detection_rate(self):
        FeedDetectionState.objects.create(
            feed=self.feed,
            frame_number=711,
            inference_ms=39.4,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("vision:video_feed_detail", args=(self.feed.pk,))
        )

        self.assertContains(response, "Detection active · 2 FPS")
        self.assertNotContains(response, "frame 711")
        self.assertNotContains(response, "39.4ms")

    def test_preview_endpoint_requires_login(self):
        response = self.client.get(
            reverse("vision:video_feed_preview", args=(self.feed.pk,))
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_preview_returns_latest_jpeg_without_exposing_source(self):
        image_path = Path(self.preview_directory.name) / f"feed-{self.feed.pk}.jpg"
        image_path.write_bytes(b"jpeg-data")
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("vision:video_feed_preview", args=(self.feed.pk,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/jpeg")
        self.assertEqual(b"".join(response.streaming_content), b"jpeg-data")
        self.assertNotContains(response, self.feed.rtsp_url)

    def test_preview_returns_no_content_while_waiting_or_paused(self):
        self.client.force_login(self.user)
        preview_url = reverse("vision:video_feed_preview", args=(self.feed.pk,))

        self.assertEqual(self.client.get(preview_url).status_code, 204)
        self.feed.is_enabled = False
        self.feed.save(update_fields=("is_enabled",))
        (Path(self.preview_directory.name) / f"feed-{self.feed.pk}.jpg").write_bytes(
            b"stale-preview"
        )

        self.assertEqual(self.client.get(preview_url).status_code, 204)

    def test_unknown_preview_returns_not_found(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("vision:video_feed_preview", args=(999,)))

        self.assertEqual(response.status_code, 404)

    def test_disabled_feed_detection_status_is_paused(self):
        self.feed.is_enabled = False
        self.feed.save(update_fields=("is_enabled",))
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("vision:video_feed_detections", args=(self.feed.pk,))
        )

        self.assertEqual(response.json()["status"], "paused")
        self.assertFalse(response.json()["is_active"])

    def test_disconnected_worker_status_is_reconnecting(self):
        FeedDetectionState.objects.create(
            feed=self.feed,
            frame_number=2,
            worker_status=FeedDetectionState.WorkerStatus.RECONNECTING,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("vision:video_feed_detections", args=(self.feed.pk,))
        )

        self.assertEqual(response.json()["status"], "reconnecting")

    def test_connected_feed_with_old_detection_is_stale(self):
        state = FeedDetectionState.objects.create(
            feed=self.feed,
            frame_number=2,
            worker_status=FeedDetectionState.WorkerStatus.CONNECTED,
        )
        FeedDetectionState.objects.filter(pk=state.pk).update(
            updated_at=timezone.now() - timedelta(minutes=2)
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("vision:video_feed_detections", args=(self.feed.pk,))
        )

        self.assertEqual(response.json()["status"], "stale")

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
