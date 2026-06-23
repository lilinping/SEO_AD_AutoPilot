"""Multi-channel messaging integration.

Inspired by OpenClaw's multi-channel support:
- Telegram Bot API
- WhatsApp Business API
- WeChat Work API
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class MessageChannel(ABC):
    """Base class for messaging channels."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    def send_message(self, chat_id: str, message: str) -> bool:
        """Send a message to a chat."""
        pass
    
    @abstractmethod
    def send_image(self, chat_id: str, image_url: str, caption: str = "") -> bool:
        """Send an image to a chat."""
        pass
    
    def is_configured(self) -> bool:
        """Check if channel is configured."""
        return True


@dataclass
class TelegramChannel(MessageChannel):
    """Telegram Bot API integration."""
    
    bot_token: str = ""
    base_url: str = "https://api.telegram.org"
    
    @property
    def name(self) -> str:
        return "Telegram"
    
    def is_configured(self) -> bool:
        return bool(self.bot_token)
    
    def send_message(self, chat_id: str, message: str) -> bool:
        """Send message via Telegram Bot API."""
        if not self.is_configured():
            return False
        
        url = f"{self.base_url}/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
        }
        
        try:
            data = json.dumps(payload).encode("utf-8")
            request = Request(url, data=data, headers={"Content-Type": "application/json"})
            with urlopen(request, timeout=10) as response:
                return response.status == 200
        except Exception as e:
            print(f"[Telegram] Error: {e}")
            return False
    
    def send_image(self, chat_id: str, image_url: str, caption: str = "") -> bool:
        """Send image via Telegram Bot API."""
        if not self.is_configured():
            return False
        
        url = f"{self.base_url}/bot{self.bot_token}/sendPhoto"
        payload = {
            "chat_id": chat_id,
            "photo": image_url,
            "caption": caption,
        }
        
        try:
            data = json.dumps(payload).encode("utf-8")
            request = Request(url, data=data, headers={"Content-Type": "application/json"})
            with urlopen(request, timeout=10) as response:
                return response.status == 200
        except Exception as e:
            print(f"[Telegram] Error: {e}")
            return False
    
    def send_report(self, chat_id: str, report_data: dict[str, Any]) -> bool:
        """Send a formatted report to Telegram."""
        message = self._format_report(report_data)
        return self.send_message(chat_id, message)
    
    def _format_report(self, data: dict[str, Any]) -> str:
        """Format report data for Telegram."""
        lines = [
            "📊 <b>SEO-AD Analysis Report</b>",
            "",
            f"🌐 URL: {data.get('url', 'N/A')}",
            f"📈 GEO Score: {data.get('geo_score', 0):.1f}/100",
            f"💰 Ad Grade: {data.get('ad_grade', 'N/A')}",
            "",
            "📝 <b>Recommendations:</b>",
        ]
        
        for rec in data.get("recommendations", [])[:5]:
            lines.append(f"• {rec}")
        
        return "\n".join(lines)


@dataclass
class WhatsAppChannel(MessageChannel):
    """WhatsApp Business API integration."""
    
    access_token: str = ""
    phone_number_id: str = ""
    base_url: str = "https://graph.facebook.com/v17.0"
    
    @property
    def name(self) -> str:
        return "WhatsApp"
    
    def is_configured(self) -> bool:
        return bool(self.access_token and self.phone_number_id)
    
    def send_message(self, chat_id: str, message: str) -> bool:
        """Send message via WhatsApp Business API."""
        if not self.is_configured():
            return False
        
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": chat_id,
            "type": "text",
            "text": {"body": message},
        }
        
        try:
            data = json.dumps(payload).encode("utf-8")
            request = Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.access_token}",
                },
            )
            with urlopen(request, timeout=10) as response:
                return response.status == 200
        except Exception as e:
            print(f"[WhatsApp] Error: {e}")
            return False
    
    def send_image(self, chat_id: str, image_url: str, caption: str = "") -> bool:
        """Send image via WhatsApp Business API."""
        # WhatsApp requires media upload first, then send by media ID
        # Simplified for demo
        return self.send_message(chat_id, f"📷 Image: {image_url}\n{caption}")


@dataclass
class WeChatWorkChannel(MessageChannel):
    """WeChat Work (企业微信) webhook integration."""
    
    webhook_url: str = ""
    
    @property
    def name(self) -> str:
        return "WeChatWork"
    
    def is_configured(self) -> bool:
        return bool(self.webhook_url)
    
    def send_message(self, chat_id: str, message: str) -> bool:
        """Send message via WeChat Work webhook."""
        if not self.is_configured():
            return False
        
        payload = {
            "msgtype": "text",
            "text": {"content": message},
        }
        
        try:
            data = json.dumps(payload).encode("utf-8")
            request = Request(self.webhook_url, data=data, headers={"Content-Type": "application/json"})
            with urlopen(request, timeout=10) as response:
                return response.status == 200
        except Exception as e:
            print(f"[WeChatWork] Error: {e}")
            return False
    
    def send_image(self, chat_id: str, image_url: str, caption: str = "") -> bool:
        """Send image via WeChat Work webhook."""
        # WeChat Work webhook supports markdown
        message = f"![image]({image_url})\n{caption}"
        return self.send_message(chat_id, message)
    
    def send_markdown(self, message: str) -> bool:
        """Send markdown message via WeChat Work webhook."""
        if not self.is_configured():
            return False
        
        payload = {
            "msgtype": "markdown",
            "markdown": {"content": message},
        }
        
        try:
            data = json.dumps(payload).encode("utf-8")
            request = Request(self.webhook_url, data=data, headers={"Content-Type": "application/json"})
            with urlopen(request, timeout=10) as response:
                return response.status == 200
        except Exception as e:
            print(f"[WeChatWork] Error: {e}")
            return False


class MultiChannelManager:
    """Manager for multi-channel messaging."""
    
    def __init__(self):
        self._channels: dict[str, MessageChannel] = {}
    
    def register(self, channel: MessageChannel) -> None:
        """Register a messaging channel."""
        self._channels[channel.name] = channel
    
    def send(self, channel_name: str, chat_id: str, message: str) -> bool:
        """Send message via specified channel."""
        channel = self._channels.get(channel_name)
        if not channel or not channel.is_configured():
            return False
        return channel.send_message(chat_id, message)
    
    def send_to_all(self, message: str, chat_ids: Optional[dict[str, str]] = None) -> dict[str, bool]:
        """Send message to all configured channels."""
        results = {}
        for name, channel in self._channels.items():
            if channel.is_configured():
                chat_id = (chat_ids or {}).get(name, "")
                if chat_id:
                    results[name] = channel.send_message(chat_id, message)
        return results
    
    def get_configured_channels(self) -> list[str]:
        """Get list of configured channels."""
        return [name for name, ch in self._channels.items() if ch.is_configured()]


def create_default_channel_manager() -> MultiChannelManager:
    """Create a channel manager with default channels."""
    import os
    
    manager = MultiChannelManager()
    
    # Telegram
    telegram_token = os.getenv("SEO_AD_BOT_TELEGRAM_BOT_TOKEN", "")
    if telegram_token:
        manager.register(TelegramChannel(bot_token=telegram_token))
    
    # WhatsApp
    whatsapp_token = os.getenv("SEO_AD_BOT_WHATSAPP_ACCESS_TOKEN", "")
    whatsapp_phone = os.getenv("SEO_AD_BOT_WHATSAPP_PHONE_NUMBER_ID", "")
    if whatsapp_token and whatsapp_phone:
        manager.register(WhatsAppChannel(
            access_token=whatsapp_token,
            phone_number_id=whatsapp_phone,
        ))
    
    # WeChat Work
    wechat_webhook = os.getenv("SEO_AD_BOT_WECHAT_WORK_WEBHOOK_URL", "")
    if wechat_webhook:
        manager.register(WeChatWorkChannel(webhook_url=wechat_webhook))
    
    return manager
