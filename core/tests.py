from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


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
