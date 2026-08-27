from pathlib import Path

path = Path("desktop/restaurant_manager/server.py")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, got {count}")
    text = text.replace(old, new, 1)


replace_once(
    "from .database import Database\n",
    "from .database import Database\nfrom .configuration_v6 import change_password_v6, load_settings_v6, patch_settings_v6, verify_unlock_v6\n",
    "configuration imports",
)

replace_once(
'''    def _backup_dir(self, state: Dict[str, Any] | None = None) -> Path:
        state = state or self.database.load()
        configured = str(state.get("settings", {}).get("backupDir", "")).strip()
        return Path(configured) if configured else default_backup_dir()
''',
'''    def _backup_dir(self, state: Dict[str, Any] | None = None) -> Path:
        source = load_settings_v6(self.database) if state is None else state
        settings = source.get("settings", source) if isinstance(source, dict) else {}
        configured = str(settings.get("backupDir", "")).strip()
        return Path(configured) if configured else default_backup_dir()
''',
    "backup dir",
)

replace_once(
'''    def maybe_auto_backup(self) -> None:
        state = self.database.load()
        settings = state["settings"]
        today = date.today().isoformat()
        now = datetime.now().strftime("%H:%M")
        if settings.get("lastAutoBackupDate") != today and now >= settings.get("backupTime", "08:00"):
            self.database.backup(self._backup_dir(state), "auto")
            settings["lastAutoBackupDate"] = today
            self.database.save(state, "auto_backup")
            self.prune_backups(state)
''',
'''    def maybe_auto_backup(self) -> None:
        settings = load_settings_v6(self.database)
        today = date.today().isoformat()
        now = datetime.now().strftime("%H:%M")
        if settings.get("lastAutoBackupDate") != today and now >= settings.get("backupTime", "08:00"):
            self.database.backup(self._backup_dir(settings), "auto")
            settings["lastAutoBackupDate"] = today
            patch_settings_v6(self.database, {"lastAutoBackupDate": today}, "auto_backup")
            self.prune_backups(settings)
''',
    "auto backup",
)

replace_once(
'''    def prune_backups(self, state: Dict[str, Any] | None = None) -> None:
        state = state or self.database.load()
        keep_days = max(7, int(state.get("settings", {}).get("backupKeepDays", 30)))
        cutoff = datetime.now() - timedelta(days=keep_days)
        for item in self._backup_dir(state).glob("restaurant_*.db"):
            if datetime.fromtimestamp(item.stat().st_mtime) < cutoff:
                item.unlink(missing_ok=True)
''',
'''    def prune_backups(self, state: Dict[str, Any] | None = None) -> None:
        source = load_settings_v6(self.database) if state is None else state
        settings = source.get("settings", source) if isinstance(source, dict) else {}
        keep_days = max(7, int(settings.get("backupKeepDays", 30)))
        cutoff = datetime.now() - timedelta(days=keep_days)
        for item in self._backup_dir(settings).glob("restaurant_*.db"):
            if datetime.fromtimestamp(item.stat().st_mtime) < cutoff:
                item.unlink(missing_ok=True)
''',
    "prune backups",
)

replace_once(
    '        settings = dict(self.database.load().get("settings", {}))\n',
    '        settings = dict(load_settings_v6(self.database))\n',
    "shortcut settings",
)

replace_once(
'''    def change_password(self, current: str, new: str) -> None:
        state = self.database.load()
        encoded = state.get("settings", {}).get("passwordHash", "")
        if encoded and not verify_password(current, encoded):
            raise ValueError("当前密码不正确")
        state["settings"]["passwordHash"] = hash_password(new)
        self.database.save(state, "change_password")

    def unlock(self, password: str) -> bool:
        encoded = self.database.load().get("settings", {}).get("passwordHash", "")
        return not encoded or verify_password(password, encoded)
''',
'''    def change_password(self, current: str, new: str) -> None:
        change_password_v6(self.database, current, new)

    def unlock(self, password: str) -> bool:
        return verify_unlock_v6(self.database, password)
''',
    "security service methods",
)

replace_once(
'''            if self.path == "/api/backup":
                configured = str(body.get("targetDir", "")).strip()
                state = self.service.database.load()
                if configured and configured != str(state.get("settings", {}).get("backupDir", "")):
                    state["settings"]["backupDir"] = configured
                    state = self.service.database.save(state, "set_backup_directory")
                target_dir = self.service._backup_dir(state)
                target = self.service.database.backup(target_dir, "manual")
                self.service.prune_backups(state)
                return self._json({"ok": True, "path": str(target), "items": self.service.backup_list()})
''',
'''            if self.path == "/api/backup":
                configured = str(body.get("targetDir", "")).strip()
                settings = load_settings_v6(self.service.database)
                if configured and configured != str(settings.get("backupDir", "")):
                    settings = patch_settings_v6(self.service.database, {"backupDir": configured}, "set_backup_directory")
                target_dir = self.service._backup_dir(settings)
                target = self.service.database.backup(target_dir, "manual")
                self.service.prune_backups(settings)
                return self._json({"ok": True, "path": str(target), "items": self.service.backup_list()})
''',
    "manual backup",
)

path.write_text(text, encoding="utf-8")
print("server.py lightweight settings wiring updated")
