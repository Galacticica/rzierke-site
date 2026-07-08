"""
File: settings_e2e.py
Description: Settings for the Playwright e2e suite. Same as the unit test
settings but serves real built Vite assets: run `npm run build` first, then
`uv run pytest -m e2e --ds=conf.settings_e2e`.
"""

from conf.settings_test import *  # noqa: F401,F403

DJANGO_VITE = {
    "default": {
        "dev_mode": False,
        # django-vite's default manifest location is under STATIC_ROOT, which
        # only exists after collectstatic; point at the build output directly.
        "manifest_path": BASE_DIR / "static" / "dist" / "manifest.json",  # noqa: F405
    }
}
