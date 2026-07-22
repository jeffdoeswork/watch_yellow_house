from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.templatetags.static import static
from django.test import SimpleTestCase, override_settings


DEFAULT_STORAGE = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}
MANIFEST_STORAGE = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
    },
}


class StaticAssetStorageTests(SimpleTestCase):
    @override_settings(DEBUG=True, STORAGES=DEFAULT_STORAGE)
    def test_development_uses_plain_static_urls_without_collectstatic(self):
        self.assertEqual(
            static("js/feed-detections.js"),
            "/static/js/feed-detections.js",
        )

    def test_production_manifest_hash_changes_with_asset_contents(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            destination = root / "collected"
            source.mkdir()
            asset = source / "mobile-controls.js"
            asset.write_text("const version = 1;", encoding="utf-8")

            with override_settings(
                DEBUG=False,
                STATIC_ROOT=destination,
                STATICFILES_DIRS=[source],
                STORAGES=MANIFEST_STORAGE,
            ):
                call_command("collectstatic", interactive=False, verbosity=0)
                first_url = static("mobile-controls.js")

                asset.write_text("const version = 2;", encoding="utf-8")
                call_command("collectstatic", interactive=False, verbosity=0)
                second_url = static("mobile-controls.js")

                self.assertRegex(
                    first_url,
                    r"^/static/mobile-controls\.[0-9a-f]{12}\.js$",
                )
                self.assertRegex(
                    second_url,
                    r"^/static/mobile-controls\.[0-9a-f]{12}\.js$",
                )
                self.assertNotEqual(first_url, second_url)
                self.assertTrue((destination / "staticfiles.json").exists())
