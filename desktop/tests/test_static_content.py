from pathlib import Path

from restaurant_manager.server import static_content_type


def test_javascript_uses_module_compatible_content_type():
    assert static_content_type(Path("app.js")) == "application/javascript; charset=utf-8"


def test_desktop_text_assets_have_explicit_utf8_types():
    assert static_content_type(Path("index.html")) == "text/html; charset=utf-8"
    assert static_content_type(Path("app.css")) == "text/css; charset=utf-8"
