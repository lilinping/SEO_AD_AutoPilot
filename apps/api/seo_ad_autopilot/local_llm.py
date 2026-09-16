"""Local LLM support — Phase 2 (GAP-018).

Supports private/self-hosted LLM deployments via:
1. Ollama   — http://localhost:11434 (or OLLAMA_BASE_URL)
2. vLLM     — OpenAI-compatible endpoint (VLLM_BASE_URL)
3. LM Studio — OpenAI-compatible endpoint (LM_STUDIO_BASE_URL)

Usage (via LLMCostRouter or direct):
    from .local_llm import LocalLLMClient, list_available_models

    client = LocalLLMClient(provider="ollama", model="llama3:8b")
    text = await client.generate("Write an FAQ about SEO...")
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Optional


# ── Provider configuration ────────────────────────────────────────────────────

_PROVIDER_DEFAULTS = {
    "ollama":    {"base_url": "http://localhost:11434", "env_key": "OLLAMA_BASE_URL"},
    "vllm":      {"base_url": "http://localhost:8000",  "env_key": "VLLM_BASE_URL"},
    "lm_studio": {"base_url": "http://localhost:1234",  "env_key": "LM_STUDIO_BASE_URL"},
}

# Default model per provider (overridable via env)
_DEFAULT_MODELS = {
    "ollama":    os.getenv("OLLAMA_DEFAULT_MODEL",     "llama3:8b"),
    "vllm":      os.getenv("VLLM_DEFAULT_MODEL",       "mistral-7b-instruct"),
    "lm_studio": os.getenv("LM_STUDIO_DEFAULT_MODEL",  "local-model"),
}


def _get_base_url(provider: str) -> str:
    cfg = _PROVIDER_DEFAULTS.get(provider)
    if not cfg:
        raise ValueError(f"Unknown local LLM provider: {provider!r}. "
                         f"Supported: {list(_PROVIDER_DEFAULTS)}")
    return os.getenv(cfg["env_key"], cfg["base_url"])


# ── Async HTTP helper ─────────────────────────────────────────────────────────

async def _post_json(url: str, payload: dict, timeout: float = 120.0) -> dict:
    try:
        import httpx
    except ImportError:
        raise ImportError("httpx is required for local LLM support: pip install httpx")

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()


async def _get_json(url: str, timeout: float = 10.0) -> Any:
    try:
        import httpx
    except ImportError:
        raise ImportError("httpx is required: pip install httpx")

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


# ── LocalLLMClient ────────────────────────────────────────────────────────────

class LocalLLMClient:
    """Unified async client for Ollama / vLLM / LM Studio.

    Args:
        provider:  "ollama" | "vllm" | "lm_studio"
        model:     Model name (e.g. "llama3:8b", "mistral-7b-instruct")
        base_url:  Override the default base URL
    """

    def __init__(
        self,
        provider: str = "ollama",
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        if provider not in _PROVIDER_DEFAULTS:
            raise ValueError(f"Unknown provider {provider!r}. "
                             f"Supported: {list(_PROVIDER_DEFAULTS)}")
        self.provider  = provider
        self.model     = model or _DEFAULT_MODELS.get(provider, "llama3:8b")
        self.base_url  = (base_url or _get_base_url(provider)).rstrip("/")

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Generate text completion for the given prompt."""
        if self.provider == "ollama":
            return await self._generate_ollama(prompt, max_tokens, temperature, system_prompt)
        else:
            # vLLM and LM Studio expose an OpenAI-compatible /v1/chat/completions endpoint
            return await self._generate_openai_compat(prompt, max_tokens, temperature, system_prompt)

    async def _generate_ollama(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        system_prompt: Optional[str],
    ) -> str:
        """Call Ollama /api/generate endpoint."""
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        payload = {
            "model":  self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }
        try:
            data = await _post_json(f"{self.base_url}/api/generate", payload)
            return data.get("response", "")
        except Exception as exc:
            raise RuntimeError(
                f"Ollama generate failed (model={self.model}, url={self.base_url}): {exc}"
            ) from exc

    async def _generate_openai_compat(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        system_prompt: Optional[str],
    ) -> str:
        """Call OpenAI-compatible /v1/chat/completions endpoint (vLLM / LM Studio)."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model":       self.model,
            "messages":    messages,
            "max_tokens":  max_tokens,
            "temperature": temperature,
        }
        try:
            data = await _post_json(f"{self.base_url}/v1/chat/completions", payload)
            choices = data.get("choices", [])
            if not choices:
                return ""
            return choices[0].get("message", {}).get("content", "")
        except Exception as exc:
            raise RuntimeError(
                f"{self.provider} generate failed (model={self.model}, url={self.base_url}): {exc}"
            ) from exc

    async def list_models(self) -> list[str]:
        """Return list of available models from the provider."""
        try:
            if self.provider == "ollama":
                data = await _get_json(f"{self.base_url}/api/tags")
                return [m["name"] for m in data.get("models", [])]
            else:
                data = await _get_json(f"{self.base_url}/v1/models")
                return [m["id"] for m in data.get("data", [])]
        except Exception:
            return []

    async def health_check(self) -> dict[str, Any]:
        """Check if the local LLM server is reachable."""
        try:
            if self.provider == "ollama":
                data = await _get_json(f"{self.base_url}/api/tags", timeout=5.0)
                models = [m["name"] for m in data.get("models", [])]
                return {
                    "provider": self.provider,
                    "base_url": self.base_url,
                    "status": "ok",
                    "model": self.model,
                    "available_models": models,
                    "model_loaded": self.model in models,
                }
            else:
                data = await _get_json(f"{self.base_url}/v1/models", timeout=5.0)
                models = [m["id"] for m in data.get("data", [])]
                return {
                    "provider": self.provider,
                    "base_url": self.base_url,
                    "status": "ok",
                    "model": self.model,
                    "available_models": models,
                    "model_loaded": self.model in models,
                }
        except Exception as exc:
            return {
                "provider": self.provider,
                "base_url": self.base_url,
                "status": "unreachable",
                "error": str(exc),
            }


# ── Convenience helpers ───────────────────────────────────────────────────────

async def list_available_models(provider: str = "ollama") -> list[str]:
    """List all available models for a local LLM provider."""
    client = LocalLLMClient(provider=provider)
    return await client.list_models()


async def health_check_all() -> dict[str, Any]:
    """Check health of all configured local LLM providers."""
    results = await asyncio.gather(
        *[LocalLLMClient(p).health_check() for p in _PROVIDER_DEFAULTS],
        return_exceptions=True,
    )
    return {
        provider: (r if not isinstance(r, Exception) else {"status": "error", "error": str(r)})
        for provider, r in zip(_PROVIDER_DEFAULTS.keys(), results)
    }


def is_local_llm_enabled() -> bool:
    """Return True if at least one local LLM provider URL is configured."""
    return any(
        os.getenv(cfg["env_key"])
        for cfg in _PROVIDER_DEFAULTS.values()
    )


def get_local_llm_client(
    preferred_provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Optional[LocalLLMClient]:
    """Return a LocalLLMClient if a provider is configured, else None."""
    providers_to_try = (
        [preferred_provider] if preferred_provider
        else list(_PROVIDER_DEFAULTS.keys())
    )
    for provider in providers_to_try:
        cfg = _PROVIDER_DEFAULTS.get(provider)
        if cfg and os.getenv(cfg["env_key"]):
            return LocalLLMClient(provider=provider, model=model)
    return None
