"""Search Engine API Integration - 真实搜索引擎 API 集成

将真实的 Google Custom Search API 和 Bing Web Search API 集成到分析流水线中。
当 API Key 未配置时，回退到基于规则的分析。
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _load_env():
    """加载 .env 文件中的环境变量"""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value  # 总是覆盖环境变量


class SearchEngineAPI:
    """搜索引擎 API 集成"""
    
    def __init__(self):
        _load_env()  # 加载 .env 文件
        self.google_api_key = os.getenv("SEO_AD_BOT_GOOGLE_API_KEY", "")
        self.google_cx = os.getenv("SEO_AD_BOT_GOOGLE_CX", "")
        self.bing_api_key = os.getenv("SEO_AD_BOT_BING_API_KEY", "")
    
    def is_google_configured(self) -> bool:
        """检查 Google API 是否已配置"""
        return bool(self.google_api_key and self.google_cx)
    
    def is_bing_configured(self) -> bool:
        """检查 Bing API 是否已配置"""
        return bool(self.bing_api_key)
    
    def search_google(self, query: str, num_results: int = 10) -> list[dict]:
        """使用 Google Custom Search API 搜索"""
        if not self.is_google_configured():
            return []
        
        params = {
            "key": self.google_api_key,
            "cx": self.google_cx,
            "q": query,
            "num": num_results,
        }
        
        try:
            url = f"https://www.googleapis.com/customsearch/v1?{urlencode(params)}"
            request = Request(url, headers={"User-Agent": "SEO-AD-AutoPilot/1.0"})
            
            with urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
            
            results = []
            for i, item in enumerate(data.get("items", []), 1):
                results.append({
                    "position": i,
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "displayLink": item.get("displayLink", ""),
                })
            
            return results
        
        except (HTTPError, json.JSONDecodeError, Exception) as e:
            print(f"[Google API] Error: {e}")
            return []
    
    def search_bing(self, query: str, num_results: int = 10) -> list[dict]:
        """使用 Bing Web Search API 搜索"""
        if not self.is_bing_configured():
            return []
        
        params = {
            "q": query,
            "count": num_results,
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
            
            results = []
            web_pages = data.get("webPages", {}).get("value", [])
            
            for i, item in enumerate(web_pages, 1):
                results.append({
                    "position": i,
                    "title": item.get("name", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("snippet", ""),
                    "dateLastCrawled": item.get("dateLastCrawled", ""),
                })
            
            return results
        
        except (HTTPError, json.JSONDecodeError, Exception) as e:
            print(f"[Bing API] Error: {e}")
            return []
    
    def get_site_search_results(self, url: str) -> dict[str, Any]:
        """获取网站在各搜索引擎中的搜索结果"""
        results = {
            "google": [],
            "bing": [],
            "google_configured": self.is_google_configured(),
            "bing_configured": self.is_bing_configured(),
        }
        
        # Google search
        if self.is_google_configured():
            query = f"site:{url}"
            results["google"] = self.search_google(query, 10)
        
        # Bing search
        if self.is_bing_configured():
            query = f"site:{url}"
            results["bing"] = self.search_bing(query, 10)
        
        return results
    
    def analyze_seo_presence(self, url: str) -> dict[str, Any]:
        """分析网站在搜索引擎中的 SEO 存在感"""
        search_results = self.get_site_search_results(url)
        
        analysis = {
            "google": {
                "configured": search_results["google_configured"],
                "results_count": len(search_results["google"]),
                "has_results": len(search_results["google"]) > 0,
                "top_result": search_results["google"][0] if search_results["google"] else None,
            },
            "bing": {
                "configured": search_results["bing_configured"],
                "results_count": len(search_results["bing"]),
                "has_results": len(search_results["bing"]) > 0,
                "top_result": search_results["bing"][0] if search_results["bing"] else None,
            },
            "overall_presence": "unknown",
        }
        
        # Determine overall presence
        if analysis["google"]["has_results"] or analysis["bing"]["has_results"]:
            analysis["overall_presence"] = "indexed"
        elif not analysis["google"]["configured"] and not analysis["bing"]["configured"]:
            analysis["overall_presence"] = "api_not_configured"
        else:
            analysis["overall_presence"] = "not_indexed"
        
        return analysis
    
    def generate_seo_recommendations(self, url: str, search_analysis: dict[str, Any]) -> list[dict[str, Any]]:
        """基于搜索引擎分析结果生成 SEO 建议"""
        recommendations = []
        
        # Google recommendations
        if search_analysis["google"]["configured"]:
            if not search_analysis["google"]["has_results"]:
                recommendations.append({
                    "engine": "Google",
                    "priority": "high",
                    "title": "网站未被 Google 收录",
                    "description": "在 Google 中搜索 site:URL 未找到结果",
                    "actions": [
                        "提交网站到 Google Search Console",
                        "创建并提交 XML 站点地图",
                        "检查 robots.txt 是否阻止了爬虫",
                    ],
                })
            else:
                # Analyze search results
                top_result = search_results["google"][0] if search_results["google"] else None
                if top_result:
                    if len(top_result.get("title", "")) > 60:
                        recommendations.append({
                            "engine": "Google",
                            "priority": "medium",
                            "title": "搜索结果标题过长",
                            "description": f"标题有 {len(top_result['title'])} 个字符，Google 通常显示 50-60 个字符",
                            "actions": ["优化 title 标签到 50-60 字符"],
                        })
        else:
            recommendations.append({
                "engine": "Google",
                "priority": "info",
                "title": "Google API 未配置",
                "description": "配置 SEO_AD_BOT_GOOGLE_API_KEY 和 SEO_AD_BOT_GOOGLE_CX 以获取真实搜索结果",
                "actions": ["在 .env 文件中配置 Google API Key"],
            })
        
        # Bing recommendations
        if search_analysis["bing"]["configured"]:
            if not search_analysis["bing"]["has_results"]:
                recommendations.append({
                    "engine": "Bing",
                    "priority": "medium",
                    "title": "网站未被 Bing 收录",
                    "description": "在 Bing 中搜索 site:URL 未找到结果",
                    "actions": [
                        "提交网站到 Bing Webmaster Tools",
                        "创建并提交 XML 站点地图",
                    ],
                })
        else:
            recommendations.append({
                "engine": "Bing",
                "priority": "info",
                "title": "Bing API 未配置",
                "description": "配置 SEO_AD_BOT_BING_API_KEY 以获取真实搜索结果",
                "actions": ["在 .env 文件中配置 Bing API Key"],
            })
        
        return recommendations


# 全局实例
search_engine_api = SearchEngineAPI()
