from pathlib import Path

import base64
import io
import json
import re

import pytest

from PIL import Image

from restaurant_manager.server import (
    icon_data_url_to_ico,
    logo_data_url,
    release_update_info,
    safe_shortcut_name,
    static_content_type,
)
from restaurant_manager.version import APP_VERSION


def test_javascript_uses_module_compatible_content_type():
    assert static_content_type(Path("app.js")) == "application/javascript; charset=utf-8"


def test_desktop_text_assets_have_explicit_utf8_types():
    assert static_content_type(Path("index.html")) == "text/html; charset=utf-8"
    assert static_content_type(Path("app.css")) == "text/css; charset=utf-8"


def test_logo_is_encoded_as_data_url(tmp_path: Path):
    logo = tmp_path / "logo.png"
    logo.write_bytes(b"small-logo")

    assert logo_data_url(logo) == f"data:image/png;base64,{base64.b64encode(b'small-logo').decode('ascii')}"


def test_logo_rejects_unsupported_files(tmp_path: Path):
    logo = tmp_path / "logo.gif"
    logo.write_bytes(b"gif")

    with pytest.raises(ValueError, match="PNG 或 JPG"):
        logo_data_url(logo)


def test_release_update_info_compares_versions():
    result = release_update_info({
        "tag_name": "v1.1.0",
        "html_url": "https://github.com/txdier/restaurant-operations-manager/releases/tag/v1.1.0",
        "name": "Version 1.1.0",
    }, current_version="1.0.9")

    assert result["hasUpdate"] is True
    assert result["latestVersion"] == "1.1.0"


def test_shortcut_name_is_safe():
    assert safe_shortcut_name('  我的/餐馆:*  ') == "我的 餐馆"


def test_logo_can_be_converted_to_windows_icon(tmp_path: Path):
    source = io.BytesIO()
    Image.new("RGBA", (64, 64), "#10af85").save(source, format="PNG")
    target = tmp_path / "desktop.ico"

    icon_data_url_to_ico(f"data:image/png;base64,{base64.b64encode(source.getvalue()).decode('ascii')}", target)

    assert target.exists()
    assert target.stat().st_size > 0


def test_installer_does_not_create_default_desktop_shortcut():
    root = Path(__file__).resolve().parents[2]
    installer = (root / "desktop" / "installer.iss").read_text(encoding="utf-8")

    assert "{autodesktop}" not in installer.lower()
    assert 'Name: "desktopicon"' not in installer


def test_desktop_versions_stay_aligned():
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / "desktop" / "app-manifest.json").read_text(encoding="utf-8"))
    installer = (root / "desktop" / "installer.iss").read_text(encoding="utf-8")
    match = re.search(r'#define MyAppVersion "([^"]+)"', installer)

    assert match is not None
    assert manifest["version"] == APP_VERSION == match.group(1)
