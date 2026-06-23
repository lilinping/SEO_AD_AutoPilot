"""Multi-channel notification system.

Supports:
- Webhook (generic HTTP)
- Email (SMTP)
- Slack
- Discord
- Telegram
"""

from __future__ import annotations

import json
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError


class NotificationChannel(ABC):
    """Base class for notification channels."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    def send(self, title: str, message: str, severity: str = "info") -> bool:
        """Send notification. Returns True if successful."""
        pass
    
    def is_configured(self) -> bool:
        """Check if channel is configured."""
        return True


@dataclass
class WebhookChannel(NotificationChannel):
    """Generic webhook notification channel."""
    
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    
    @property
    def name(self) -> str:
        return "Webhook"
    
    def is_configured(self) -> bool:
        return bool(self.url)
    
    def send(self, title: str, message: str, severity: str = "info") -> bool:
        if not self.is_configured():
            return False
        
        payload = {
            "title": title,
            "message": message,
            "severity": severity,
        }
        
        try:
            data = json.dumps(payload).encode("utf-8")
            request = Request(
                self.url,
                data=data,
                headers={"Content-Type": "application/json", **self.headers},
                method="POST",
            )
            with urlopen(request, timeout=10) as response:
                return response.status == 200
        except (HTTPError, Exception) as e:
            print(f"[Webhook] Error: {e}")
            return False


@dataclass
class EmailChannel(NotificationChannel):
    """Email notification channel via SMTP."""
    
    smtp_host: str = ""
    smtp_port: int = 587
    username: str = ""
    password: str = ""
    from_addr: str = ""
    to_addrs: list[str] = field(default_factory=list)
    use_tls: bool = True
    
    @property
    def name(self) -> str:
        return "Email"
    
    def is_configured(self) -> bool:
        return bool(self.smtp_host and self.from_addr and self.to_addrs)
    
    def send(self, title: str, message: str, severity: str = "info") -> bool:
        if not self.is_configured():
            return False
        
        try:
            msg = MIMEMultipart()
            msg["From"] = self.from_addr
            msg["To"] = ", ".join(self.to_addrs)
            msg["Subject"] = f"[{severity.upper()}] {title}"
            msg.attach(MIMEText(message, "plain"))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())
            
            return True
        except Exception as e:
            print(f"[Email] Error: {e}")
            return False


@dataclass
class SlackChannel(NotificationChannel):
    """Slack notification channel via webhook."""
    
    webhook_url: str = ""
    channel: str = ""
    
    @property
    def name(self) -> str:
        return "Slack"
    
    def is_configured(self) -> bool:
        return bool(self.webhook_url)
    
    def send(self, title: str, message: str, severity: str = "info") -> bool:
        if not self.is_configured():
            return False
        
        color_map = {
            "info": "#36a64f",
            "warning": "#ff9900",
            "error": "#ff0000",
            "critical": "#ff0000",
        }
        
        payload = {
            "attachments": [{
                "color": color_map.get(severity, "#36a64f"),
                "title": title,
                "text": message,
                "footer": "SEO-AD AutoPilot",
            }]
        }
        
        if self.channel:
            payload["channel"] = self.channel
        
        try:
            data = json.dumps(payload).encode("utf-8")
            request = Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=10) as response:
                return response.status == 200
        except Exception as e:
            print(f"[Slack] Error: {e}")
            return False


@dataclass
class DiscordChannel(NotificationChannel):
    """Discord notification channel via webhook."""
    
    webhook_url: str = ""
    
    @property
    def name(self) -> str:
        return "Discord"
    
    def is_configured(self) -> bool:
        return bool(self.webhook_url)
    
    def send(self, title: str, message: str, severity: str = "info") -> bool:
        if not self.is_configured():
            return False
        
        color_map = {
            "info": 0x36a64f,
            "warning": 0xff9900,
            "error": 0xff0000,
            "critical": 0xff0000,
        }
        
        payload = {
            "embeds": [{
                "title": title,
                "description": message,
                "color": color_map.get(severity, 0x36a64f),
                "footer": {"text": "SEO-AD AutoPilot"},
            }]
        }
        
        try:
            data = json.dumps(payload).encode("utf-8")
            request = Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=10) as response:
                return response.status == 204
        except Exception as e:
            print(f"[Discord] Error: {e}")
            return False


class NotificationManager:
    """Manager for multi-channel notifications."""
    
    def __init__(self):
        self._channels: dict[str, NotificationChannel] = {}
    
    def register(self, channel: NotificationChannel) -> None:
        """Register a notification channel."""
        self._channels[channel.name] = channel
    
    def send(self, title: str, message: str, severity: str = "info") -> dict[str, bool]:
        """Send notification to all configured channels."""
        results = {}
        for name, channel in self._channels.items():
            if channel.is_configured():
                results[name] = channel.send(title, message, severity)
            else:
                results[name] = False
        return results
    
    def send_alert(self, alert_type: str, message: str) -> dict[str, bool]:
        """Send an alert notification."""
        severity_map = {
            "info": "info",
            "warning": "warning",
            "error": "error",
            "critical": "critical",
        }
        return self.send(
            title=f"SEO-AD AutoPilot Alert: {alert_type}",
            message=message,
            severity=severity_map.get(alert_type, "info"),
        )
    
    def get_configured_channels(self) -> list[str]:
        """Get list of configured channels."""
        return [
            name for name, channel in self._channels.items()
            if channel.is_configured()
        ]


def create_default_notification_manager() -> NotificationManager:
    """Create a notification manager with default channels."""
    import os
    
    manager = NotificationManager()
    
    # Webhook
    webhook_url = os.getenv("SEO_AD_BOT_ALERT_WEBHOOK_URL", "")
    if webhook_url:
        manager.register(WebhookChannel(url=webhook_url))
    
    # Email
    smtp_host = os.getenv("SEO_AD_BOT_ALERT_SMTP_HOST", "")
    if smtp_host:
        manager.register(EmailChannel(
            smtp_host=smtp_host,
            smtp_port=int(os.getenv("SEO_AD_BOT_ALERT_SMTP_PORT", "587")),
            username=os.getenv("SEO_AD_BOT_ALERT_SMTP_USERNAME", ""),
            password=os.getenv("SEO_AD_BOT_ALERT_SMTP_PASSWORD", ""),
            from_addr=os.getenv("SEO_AD_BOT_ALERT_SMTP_FROM_ADDRESS", ""),
            to_addrs=os.getenv("SEO_AD_BOT_ALERT_SMTP_TO_ADDRESSES", "").split(","),
        ))
    
    # Slack
    slack_url = os.getenv("SEO_AD_BOT_ALERT_SLACK_WEBHOOK_URL", "")
    if slack_url:
        manager.register(SlackChannel(webhook_url=slack_url))
    
    # Discord
    discord_url = os.getenv("SEO_AD_BOT_ALERT_DISCORD_WEBHOOK_URL", "")
    if discord_url:
        manager.register(DiscordChannel(webhook_url=discord_url))
    
    return manager
