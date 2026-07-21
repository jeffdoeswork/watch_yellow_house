from django.test import TestCase
from django.urls import reverse


class PublicPageTests(TestCase):
    def test_dashboard_uses_shared_layout(self):
        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "core/dashboard.html")
        self.assertContains(response, "Watch Yellow House")
        self.assertContains(response, "Primary navigation")
        self.assertContains(response, "Dashboard")

    def test_video_feeds_uses_shared_layout(self):
        response = self.client.get(reverse("core:video_feeds"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "core/video_feeds.html")
        self.assertContains(response, "Video Feeds")

    def test_demo_pages_are_removed(self):
        for path in ("/briefing/", "/timeline/", "/sources/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)
