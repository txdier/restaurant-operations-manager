from __future__ import annotations

import os
import sys
from pathlib import Path


def install_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    override = os.environ.get("RESTAURANT_MANAGER_DATA_DIR")
    if override:
        root = Path(override)
    elif sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "RestaurantManager"
    else:
        root = Path.home() / ".local/share/restaurant-manager"
    root.mkdir(parents=True, exist_ok=True)
    return root


def database_path() -> Path:
    return data_dir() / "restaurant.db"


def default_backup_dir() -> Path:
    root = data_dir() / "backups"
    root.mkdir(parents=True, exist_ok=True)
    return root


def log_dir() -> Path:
    root = data_dir() / "logs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def web_dir() -> Path:
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled) / "restaurant_manager/web"
    return Path(__file__).resolve().parent / "web"
