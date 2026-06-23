from .base import AdPlatform, AdSlot, AdRecommendation, AdPlatformType
from .adsense import AdSensePlatform
from .mediavine import MediavinePlatform
from .ezoic import EzoicPlatform
from .adthrive import AdThrivePlatform
from .monumetric import MonumetricPlatform
from .pubmatic import PubMaticPlatform
from .amazon_ads import AmazonAdsPlatform
from .auto_discovery import AdPlatformAutoDiscovery, analyze_site_for_ads

__all__ = [
    "AdPlatform",
    "AdSlot",
    "AdRecommendation",
    "AdPlatformType",
    "AdSensePlatform",
    "MediavinePlatform",
    "EzoicPlatform",
    "AdThrivePlatform",
    "MonumetricPlatform",
    "PubMaticPlatform",
    "AmazonAdsPlatform",
    "AdPlatformAutoDiscovery",
    "analyze_site_for_ads",
]
