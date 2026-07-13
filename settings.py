from __future__ import annotations

import json
import threading
from configparser import ConfigParser
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

PROJECT_ROOT: Path = Path(__file__).resolve().parent
_DEFAULT_CONFIG: Path = PROJECT_ROOT / "config" / "default_settings.ini"
_USER_CONFIG: Path = PROJECT_ROOT / "config" / "user_settings.ini"
_SOURCES_FILE: Path = PROJECT_ROOT / "config" / "sources.json"
_ENV_FILE: Path = PROJECT_ROOT / ".env"


class Settings:
    _shared_state: Dict[str, Any] = {}
    _initialised: bool = False
    _lock: threading.Lock = threading.Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> "Settings":
        instance = super().__new__(cls)
        instance.__dict__ = cls._shared_state
        return instance

    def __init__(self) -> None:
        if Settings._initialised:
            return
        with Settings._lock:
            if Settings._initialised:
                return
            if _ENV_FILE.exists():
                load_dotenv(_ENV_FILE)
            self._parser: ConfigParser = ConfigParser()
            if _DEFAULT_CONFIG.exists():
                self._parser.read(_DEFAULT_CONFIG, encoding="utf-8")
            if _USER_CONFIG.exists():
                self._parser.read(_USER_CONFIG, encoding="utf-8")
            self._sources: List[Dict[str, Any]] = self._load_sources()
            Settings._initialised = True

    @staticmethod
    def _load_sources() -> List[Dict[str, Any]]:
        if not _SOURCES_FILE.exists():
            return []
        with open(_SOURCES_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("sources", [])

    @property
    def news_sources(self) -> List[Dict[str, Any]]:
        return list(self._sources)

    def _get(self, section: str, key: str, fallback: str = "") -> str:
        return self._parser.get(section, key, fallback=fallback)

    def _get_int(self, section: str, key: str, fallback: int = 0) -> int:
        return self._parser.getint(section, key, fallback=fallback)

    def _get_float(self, section: str, key: str, fallback: float = 0.0) -> float:
        return self._parser.getfloat(section, key, fallback=fallback)

    def _get_bool(self, section: str, key: str, fallback: bool = False) -> bool:
        return self._parser.getboolean(section, key, fallback=fallback)

    def _get_path(self, section: str, key: str, fallback: str = "") -> Path:
        raw = self._get(section, key, fallback)
        return PROJECT_ROOT / raw if raw else PROJECT_ROOT

    def _set(self, section: str, key: str, value: Any) -> None:
        with Settings._lock:
            if not self._parser.has_section(section):
                self._parser.add_section(section)
            self._parser.set(section, key, str(value))
            self._persist()

    def _persist(self) -> None:
        _USER_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        with open(_USER_CONFIG, "w", encoding="utf-8") as fh:
            self._parser.write(fh)

    @property
    def app_name(self) -> str:
        return self._get("application", "name", "NewsScrape Pro")

    @property
    def app_version(self) -> str:
        return self._get("application", "version", "1.0.0")

    @property
    def window_width(self) -> int:
        return self._get_int("application", "window_width", 1400)

    @property
    def window_height(self) -> int:
        return self._get_int("application", "window_height", 850)

    @property
    def theme(self) -> str:
        return self._get("application", "theme", "dark")

    @theme.setter
    def theme(self, value: str) -> None:
        self._set("application", "theme", value)

    @property
    def request_timeout(self) -> int:
        return self._get_int("scraper", "request_timeout", 15)

    @request_timeout.setter
    def request_timeout(self, value: int) -> None:
        self._set("scraper", "request_timeout", value)

    @property
    def retry_count(self) -> int:
        return self._get_int("scraper", "retry_count", 3)

    @retry_count.setter
    def retry_count(self, value: int) -> None:
        self._set("scraper", "retry_count", value)

    @property
    def request_delay(self) -> float:
        return self._get_float("scraper", "request_delay", 2.0)

    @request_delay.setter
    def request_delay(self, value: float) -> None:
        self._set("scraper", "request_delay", value)

    @property
    def random_user_agent(self) -> bool:
        return self._get_bool("scraper", "random_user_agent", True)

    @property
    def respect_robots_txt(self) -> bool:
        return self._get_bool("scraper", "respect_robots_txt", True)

    @property
    def max_threads(self) -> int:
        return self._get_int("scraper", "max_threads", 4)

    @property
    def database_path(self) -> Path:
        return self._get_path("database", "path", "database/newsscrape.db")

    @property
    def auto_save(self) -> bool:
        return self._get_bool("database", "auto_save", True)

    @property
    def export_folder(self) -> Path:
        return self._get_path("export", "folder", "exports")

    @export_folder.setter
    def export_folder(self, value: str) -> None:
        self._set("export", "folder", value)

    @property
    def auto_export(self) -> bool:
        return self._get_bool("export", "auto_export", False)

    @auto_export.setter
    def auto_export(self, value: bool) -> None:
        self._set("export", "auto_export", value)

    @property
    def default_export_format(self) -> str:
        return self._get("export", "default_format", "csv")

    @property
    def scheduler_enabled(self) -> bool:
        return self._get_bool("scheduler", "enabled", False)

    @scheduler_enabled.setter
    def scheduler_enabled(self, value: bool) -> None:
        self._set("scheduler", "enabled", value)

    @property
    def scheduler_interval(self) -> int:
        return self._get_int("scheduler", "interval_minutes", 60)

    @scheduler_interval.setter
    def scheduler_interval(self, value: int) -> None:
        self._set("scheduler", "interval_minutes", value)

    @property
    def log_file(self) -> Path:
        return self._get_path("logging", "file", "logs/scraper.log")

    @property
    def log_level(self) -> str:
        return self._get("logging", "level", "INFO").upper()

    @property
    def log_max_bytes(self) -> int:
        return self._get_int("logging", "max_bytes", 5_242_880)

    @property
    def log_backup_count(self) -> int:
        return self._get_int("logging", "backup_count", 5)

    @property
    def sidebar_width(self) -> int:
        return self._get_int("ui", "sidebar_width", 220)

    @property
    def animations_enabled(self) -> bool:
        return self._get_bool("ui", "animations", True)

    @property
    def table_page_size(self) -> int:
        return self._get_int("ui", "table_page_size", 50)

    def reset_to_defaults(self) -> None:
        with Settings._lock:
            if _USER_CONFIG.exists():
                _USER_CONFIG.unlink()
            self._parser = ConfigParser()
            if _DEFAULT_CONFIG.exists():
                self._parser.read(_DEFAULT_CONFIG, encoding="utf-8")

    def __repr__(self) -> str:
        return f"<Settings theme={self.theme!r} timeout={self.request_timeout} db={self.database_path}>"
