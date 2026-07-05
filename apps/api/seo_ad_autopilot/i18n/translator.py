"""Translator core — lazy-loaded JSON locale files with ContextVar locale.

Phase 2 (GAP-011):
- All user-facing strings centralised in locales/{locale}.json
- ContextVar allows per-request locale without thread-local issues
- Fallback chain: requested locale → en → key itself
- Supports nested keys: "agent.analysis_complete"
- Supports template vars: t("greeting", name="Alice") → "Hello, Alice"
"""

from __future__ import annotations

import json
import os
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Optional

SUPPORTED_LOCALES = ["en", "zh-CN", "zh-TW", "ja", "ko", "de", "fr", "es", "pt", "ar"]

_LOCALES_DIR = Path(__file__).parent / "locales"
_locale_var: ContextVar[str] = ContextVar("locale", default="en")
_cache: dict[str, dict] = {}


def _load_locale(locale: str) -> dict:
    if locale in _cache:
        return _cache[locale]
    fp = _LOCALES_DIR / f"{locale}.json"
    if fp.exists():
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            _cache[locale] = data
            return data
        except Exception:
            pass
    _cache[locale] = {}
    return {}


def _get_nested(data: dict, key: str) -> Optional[str]:
    """Traverse nested dict with dot-notation key."""
    parts = key.split(".")
    obj = data
    for p in parts:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(p)
    return str(obj) if obj is not None else None


class Translator:
    """Locale-aware translator instance."""

    def __init__(self, locale: str = "en") -> None:
        self.locale = locale if locale in SUPPORTED_LOCALES else "en"
        self._data  = _load_locale(self.locale)
        self._en    = _load_locale("en")

    def translate(self, key: str, **kwargs: Any) -> str:
        """Return translated string for key, with optional template substitution."""
        text = _get_nested(self._data, key) or _get_nested(self._en, key) or key
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, IndexError):
                pass
        return text

    def __call__(self, key: str, **kwargs: Any) -> str:
        return self.translate(key, **kwargs)


# ── Module-level convenience functions ───────────────────────────────────────

def set_locale(locale: str) -> None:
    """Set the current-context locale (ContextVar — per request/task)."""
    if locale in SUPPORTED_LOCALES:
        _locale_var.set(locale)
    else:
        # Fuzzy match: "zh" → "zh-CN", "pt-BR" → "pt"
        base = locale.split("-")[0].lower()
        for supported in SUPPORTED_LOCALES:
            if supported.lower().startswith(base):
                _locale_var.set(supported)
                return
        _locale_var.set("en")


def get_locale() -> str:
    return _locale_var.get()


def get_translator(locale: Optional[str] = None) -> Translator:
    return Translator(locale or get_locale())


def t(key: str, locale: Optional[str] = None, **kwargs: Any) -> str:
    """Global translate shorthand."""
    return get_translator(locale).translate(key, **kwargs)
