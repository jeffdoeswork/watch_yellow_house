from django.test import TestCase
from django.urls import reverse


class PublicPageTests(TestCase):
    def test_home_page_uses_shared_layout(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertContains(response, "Watch Yellow House")
        self.assertContains(response, "Primary navigation")

    def test_navigation_pages_are_available(self):
        page_names = ("briefing", "timeline", "sources")

        for page_name in page_names:
            with self.subTest(page=page_name):
                response = self.client.get(reverse(f"core:{page_name}"))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "base.html")

