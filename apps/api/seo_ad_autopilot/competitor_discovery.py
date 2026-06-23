"""Competitor Discovery - 竞品智能发现模块

使用搜索引擎 API 搜索全网同类型的网站，分析他们是如何做 SEO/GEO 的。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


# ─── 行业关键词映射 ─────────────────────────────────────────────────────

INDUSTRY_SEARCH_KEYWORDS = {
    "ecommerce": {
        "zh": ["电商网站", "在线商店", "购物网站", "产品展示"],
        "en": ["ecommerce website", "online store", "shop", "product catalog"],
    },
    "blog": {
        "zh": ["博客网站", "内容平台", "资讯网站", "行业博客"],
        "en": ["blog", "content site", "news site", "industry blog"],
    },
    "saas": {
        "zh": ["SaaS 平台", "软件服务", "云平台", "工具网站"],
        "en": ["SaaS platform", "software service", "cloud platform", "tool website"],
    },
    "tool": {
        "zh": ["工具网站", "在线工具", "计算器", "生成器"],
        "en": ["tool website", "online tool", "calculator", "generator"],
    },
    "media": {
        "zh": ["媒体网站", "视频平台", "播客网站", "新闻门户"],
        "en": ["media website", "video platform", "podcast site", "news portal"],
    },
    "local": {
        "zh": ["本地服务", "本地商家", "门店网站", "服务预约"],
        "en": ["local service", "local business", "store website", "service booking"],
    },
    "corporate": {
        "zh": ["企业官网", "公司网站", "品牌官网", "官方网站"],
        "en": ["corporate website", "company site", "brand website", "official site"],
    },
}

# ─── 竞品发现 ─────────────────────────────────────────────────────────────

class CompetitorDiscovery:
    """竞品智能发现"""
    
    def __init__(self):
        self.google_api_key = os.getenv("SEO_AD_BOT_GOOGLE_API_KEY", "")
        self.google_cx = os.getenv("SEO_AD_BOT_GOOGLE_CX", "")
        self.bing_api_key = os.getenv("SEO_AD_BOT_BING_API_KEY", "")
    
    def discover_competitors(
        self,
        url: str,
        website_type: str,
        industry: str,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """发现竞品网站"""
        
        # 生成搜索关键词
        keywords = self._generate_search_keywords(url, website_type, industry)
        
        # 使用搜索引擎搜索
        competitors = []
        
        # Google 搜索
        if self.google_api_key:
            google_results = self._search_google(keywords, max_results)
            competitors.extend(google_results)
        
        # Bing 搜索
        if self.bing_api_key:
            bing_results = self._search_bing(keywords, max_results)
            competitors.extend(bing_results)
        
        # 去重
        seen_urls = set()
        unique_competitors = []
        for comp in competitors:
            if comp["url"] not in seen_urls and comp["url"] != url:
                seen_urls.add(comp["url"])
                unique_competitors.append(comp)
        
        return unique_competitors[:max_results]
    
    def _generate_search_keywords(
        self,
        url: str,
        website_type: str,
        industry: str,
    ) -> list[str]:
        """生成搜索关键词"""
        keywords = []
        
        # 从域名提取关键词
        domain = urlparse(url).netloc
        domain_parts = domain.replace("www.", "").split(".")[0]
        keywords.append(domain_parts)
        
        # 从行业关键词获取
        industry_keywords = INDUSTRY_SEARCH_KEYWORDS.get(website_type, {})
        keywords.extend(industry_keywords.get("zh", [])[:2])
        keywords.extend(industry_keywords.get("en", [])[:2])
        
        # 组合关键词
        search_queries = [
            f"{domain_parts} 竞品",
            f"{domain_parts} similar",
            f"{industry} website",
            f"{website_type} website examples",
        ]
        
        return search_queries[:3]  # 最多 3 个搜索查询
    
    def _search_google(self, keywords: list[str], max_results: int) -> list[dict[str, Any]]:
        """使用 Google 搜索"""
        results = []
        
        for keyword in keywords:
            params = {
                "key": self.google_api_key,
                "cx": self.google_cx,
                "q": keyword,
                "num": min(max_results, 10),
            }
            
            try:
                url = f"https://www.googleapis.com/customsearch/v1?{urlencode(params)}"
                request = Request(url, headers={"User-Agent": "SEO-AD-AutoPilot/1.0"})
                
                with urlopen(request, timeout=10) as response:
                    data = json.loads(response.read().decode("utf-8"))
                
                for item in data.get("items", []):
                    results.append({
                        "url": item.get("link", ""),
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "source": "google",
                    })
            except Exception as e:
                print(f"[Google Search] Error: {e}")
        
        return results
    
    def _search_bing(self, keywords: list[str], max_results: int) -> list[dict[str, Any]]:
        """使用 Bing 搜索"""
        results = []
        
        for keyword in keywords:
            params = {
                "q": keyword,
                "count": min(max_results, 10),
            }
            
            try:
                url = f"https://api.bing.microsoft.com/v7.0/search?{urlencode(params)}"
                request = Request(
                    url,
                    headers={
                        "Ocp-Apim-Subscription-Key": self.bing_api_key,
                        "User-Agent": "SEO-AD-AutoPilot/1.0",
                    },
                )
                
                with urlopen(request, timeout=10) as response:
                    data = json.loads(response.read().decode("utf-8"))
                
                for item in data.get("webPages", {}).get("value", []):
                    results.append({
                        "url": item.get("url", ""),
                        "title": item.get("name", ""),
                        "snippet": item.get("snippet", ""),
                        "source": "bing",
                    })
            except Exception as e:
                print(f"[Bing Search] Error: {e}")
        
        return results


# 全局实例
competitor_discovery = CompetitorDiscovery()
