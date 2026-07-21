from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from vision.models import FeedDetectionState, VideoFeed


class AuthenticationTests(TestCase):
    def test_login_page_is_public(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("core:dashboard"))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('core:dashboard')}",
        )

    def test_registration_route_does_not_exist(self):
        self.assertEqual(self.client.get("/register/").status_code, 404)

    def test_admin_login_remains_available(self):
        self.assertEqual(self.client.get(reverse("admin:login")).status_code, 200)


class AuthenticatedPageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="viewer",
            password="test-password",
        )
        self.client.force_login(self.user)

    def test_dashboard_uses_shared_layout(self):
        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "core/dashboard.html")
        self.assertContains(response, "Watch Yellow House")
        self.assertContains(response, "Primary navigation")
        self.assertContains(response, "Dashboard")

    def test_demo_pages_are_removed(self):
        for path in ("/briefing/", "/timeline/", "/sources/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_dashboard_totals_active_stabilized_feed_counts(self):
        active_feed = VideoFeed.objects.create(rtsp_url="rtsp://active.example/live")
        stale_feed = VideoFeed.objects.create(rtsp_url="rtsp://stale.example/live")
        FeedDetectionState.objects.create(
            feed=active_feed,
            stable_counts={"person": 2, "car": 1},
        )
        stale_state = FeedDetectionState.objects.create(
            feed=stale_feed,
            stable_counts={"person": 20},
        )
        FeedDetectionState.objects.filter(pk=stale_state.pk).update(
            updated_at=timezone.now() - timedelta(minutes=5)
        )

        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.context["total_objects"], 3)
        self.assertEqual(response.context["stable_counts"], {"car": 1, "person": 2})
        self.assertContains(response, "Mode of the latest 10 inference frames")

    def test_dashboard_detection_endpoint_is_authenticated(self):
        self.client.logout()

        response = self.client.get(reverse("core:detections"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
