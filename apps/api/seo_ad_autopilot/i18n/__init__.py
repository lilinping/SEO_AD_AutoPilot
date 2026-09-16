"""Internationalization (i18n) package — Phase 2 (GAP-011).

Supports: en, zh-CN, ja, ko, de, fr, es, pt, ar
Usage:
    from .i18n import t, set_locale, get_translator
    t("agent.analysis_complete")  # → "Analysis complete"
    t("agent.analysis_complete", locale="zh-CN")  # → "分析完成"
"""

from .translator import Translator, t, set_locale, get_locale, get_translator, SUPPORTED_LOCALES

__all__ = [
    "Translator",
    "t",
    "set_locale",
    "get_locale",
    "get_translator",
    "SUPPORTED_LOCALES",
]
