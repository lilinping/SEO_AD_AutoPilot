"""Web Scraper skill - real web page reading via Jina Reader (Agent-Reach pattern).

Replaces the old mock crawler with actual web content extraction.
Uses Jina Reader (free, no API key) for clean Markdown page content.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Optional
from urllib.parse import urlparse
import urllib.request
import urllib.error

from .base import Skill, SkillCategory, SkillInput, SkillOutput, SkillRiskLevel


JINA_READER_URL = "https://r.jina.ai"
_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


class WebScraperSkill(Skill):
    """Web Scraper - reads any webpage and returns clean Markdown content.

    Uses Jina Reader (free, no API key) to convert any URL into
    clean, readable Markdown. Also extracts metadata, links, and images.
    """

    @property
    def name(self) -> str:
        return "Web Scraper"

    @property
    def description(self) -> str:
        return (
            "Read any webpage and return clean Markdown content, metadata, "
            "links, and images. Uses Jina Reader (free, no API key)."
        )

    @property
    def category(self) -> SkillCategory:
        return SkillCategory.CRAWL

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.READ_ONLY

    def validate_input(self, skill_input: SkillInput) -> bool:
        return "url" in skill_input.params

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to scrape"},
                "format": {
                    "type": "string",
                    "enum": ["markdown", "text", "html"],
                    "default": "markdown",
                },
                "timeout": {"type": "integer", "default": 30},
            },
            "required": ["url"],
        }

    def execute(self, skill_input: SkillInput) -> SkillOutput:
        start_time = time.time()
        params = skill_input.params

        url = params.get("url", "")
        if not url:
            return self._create_output(
                success=False,
                error="URL is required",
            )

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        fmt = params.get("format", "markdown")
        timeout = params.get("timeout", 30)

        try:
            jina_url = f"{JINA_READER_URL}/{url}"
            req = urllib.request.Request(
                jina_url,
                headers={
                    "User-Agent": _USER_AGENT,
                    "Accept": f"text/{fmt}" if fmt != "html" else "text/html",
                },
            )

            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content = resp.read().decode("utf-8")

            parsed_url = urlparse(url)
            title = ""
            title_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()

            links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)
            images = re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", content)

            paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
            word_count = len(content.split())

            result = {
                "url": url,
                "domain": parsed_url.netloc,
                "title": title,
                "content": content,
                "word_count": word_count,
                "paragraph_count": len(paragraphs),
                "links": [{"text": text, "url": link} for text, link in links[:50]],
                "images": [{"alt": alt, "url": img} for alt, img in images[:20]],
                "metadata": {
                    "protocol": parsed_url.scheme,
                    "path": parsed_url.path,
                },
            }

            elapsed_ms = int((time.time() - start_time) * 1000)

            return self._create_output(
                success=True,
                result=result,
                execution_time_ms=elapsed_ms,
            )

        except urllib.error.HTTPError as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return self._create_output(
                success=False,
                error=f"HTTP {e.code}: {e.reason}. URL may be blocked or invalid.",
                execution_time_ms=elapsed_ms,
            )
        except urllib.error.URLError as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return self._create_output(
                success=False,
                error=f"Connection failed: {str(e.reason)}",
                execution_time_ms=elapsed_ms,
            )
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return self._create_output(
                success=False,
                error=f"Scraping failed: {str(e)}",
                execution_time_ms=elapsed_ms,
            )


class YouTubeTranscriptSkill(Skill):
    """YouTube Transcript - extracts video transcripts and metadata.

    Uses yt-dlp to extract video info and subtitles from YouTube.
    """

    @property
    def name(self) -> str:
        return "YouTube Transcript"

    @property
    def description(self) -> str:
        return (
            "Extract YouTube video transcripts, metadata, and subtitles. "
            "Requires yt-dlp installed."
        )

    @property
    def category(self) -> SkillCategory:
        return SkillCategory.CRAWL

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.READ_ONLY

    def validate_input(self, skill_input: SkillInput) -> bool:
        return "url" in skill_input.params

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "YouTube video URL"},
                "lang": {"type": "string", "default": "en", "description": "Subtitle language"},
            },
            "required": ["url"],
        }

    def execute(self, skill_input: SkillInput) -> SkillOutput:
        start_time = time.time()
        params = skill_input.params

        url = params.get("url", "")
        if not url:
            return self._create_output(
                success=False,
                error="YouTube URL is required",
            )

        try:
            import subprocess

            info_cmd = [
                "yt-dlp",
                "--dump-json",
                "--no-download",
                "--no-warnings",
                url,
            ]

            proc = subprocess.run(
                info_cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if proc.returncode != 0:
                elapsed_ms = int((time.time() - start_time) * 1000)
                return self._create_output(
                    success=False,
                    error=f"yt-dlp failed: {proc.stderr[:500]}",
                    execution_time_ms=elapsed_ms,
                )

            info = json.loads(proc.stdout)

            subtitle_cmd = [
                "yt-dlp",
                "--write-sub",
                "--write-auto-sub",
                "--sub-lang", params.get("lang", "en"),
                "--skip-download",
                "--sub-format", "vtt",
                "-o", "/tmp/yt_sub_%(id)s",
                url,
            ]

            sub_proc = subprocess.run(
                subtitle_cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            subtitle_text = ""
            video_id = info.get("id", "")
            sub_file = f"/tmp/yt_sub_{video_id}.en.vtt"
            try:
                with open(sub_file, "r") as f:
                    raw = f.read()
                    lines = []
                    for line in raw.split("\n"):
                        if line.strip() and not line.startswith("WEBVTT") and "-->" not in line and not line.strip().isdigit():
                            clean = re.sub(r"<[^>]+>", "", line).strip()
                            if clean and clean not in lines[-1:]:
                                lines.append(clean)
                    subtitle_text = " ".join(lines)
            except FileNotFoundError:
                pass

            result = {
                "url": url,
                "video_id": video_id,
                "title": info.get("title", ""),
                "description": info.get("description", "")[:2000],
                "channel": info.get("channel", ""),
                "channel_id": info.get("channel_id", ""),
                "duration": info.get("duration", 0),
                "view_count": info.get("view_count", 0),
                "like_count": info.get("like_count", 0),
                "upload_date": info.get("upload_date", ""),
                "tags": info.get("tags", [])[:20],
                "categories": info.get("categories", []),
                "thumbnail": info.get("thumbnail", ""),
                "subtitle": subtitle_text[:5000] if subtitle_text else "",
                "has_subtitle": bool(subtitle_text),
            }

            elapsed_ms = int((time.time() - start_time) * 1000)

            return self._create_output(
                success=True,
                result=result,
                execution_time_ms=elapsed_ms,
            )

        except FileNotFoundError:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return self._create_output(
                success=False,
                error="yt-dlp not installed. Run: pip install yt-dlp",
                execution_time_ms=elapsed_ms,
            )
        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return self._create_output(
                success=False,
                error="yt-dlp timed out (60s)",
                execution_time_ms=elapsed_ms,
            )
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return self._create_output(
                success=False,
                error=str(e),
                execution_time_ms=elapsed_ms,
            )


class RSSFeedSkill(Skill):
    """RSS Feed Reader - reads and parses RSS/Atom feeds."""

    @property
    def name(self) -> str:
        return "RSS Feed Reader"

    @property
    def description(self) -> str:
        return "Read and parse RSS/Atom feeds for content monitoring."

    @property
    def category(self) -> SkillCategory:
        return SkillCategory.CRAWL

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.READ_ONLY

    def validate_input(self, skill_input: SkillInput) -> bool:
        return "url" in skill_input.params

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "RSS/Atom feed URL"},
                "limit": {"type": "integer", "default": 20, "description": "Max entries to return"},
            },
            "required": ["url"],
        }

    def execute(self, skill_input: SkillInput) -> SkillOutput:
        start_time = time.time()
        params = skill_input.params

        url = params.get("url", "")
        limit = params.get("limit", 20)

        if not url:
            return self._create_output(
                success=False,
                error="Feed URL is required",
            )

        try:
            import feedparser

            feed = feedparser.parse(url)

            entries = []
            for entry in feed.entries[:limit]:
                entries.append({
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "summary": entry.get("summary", "")[:500],
                    "author": entry.get("author", ""),
                    "tags": [t.get("term", "") for t in entry.get("tags", [])],
                })

            result = {
                "url": url,
                "feed_title": feed.feed.get("title", ""),
                "feed_description": feed.feed.get("description", ""),
                "feed_link": feed.feed.get("link", ""),
                "entries": entries,
                "total_entries": len(entries),
            }

            elapsed_ms = int((time.time() - start_time) * 1000)

            return self._create_output(
                success=True,
                result=result,
                execution_time_ms=elapsed_ms,
            )

        except ImportError:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return self._create_output(
                success=False,
                error="feedparser not installed. Run: pip install feedparser",
                execution_time_ms=elapsed_ms,
            )
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return self._create_output(
                success=False,
                error=f"RSS parsing failed: {str(e)}",
                execution_time_ms=elapsed_ms,
            )
