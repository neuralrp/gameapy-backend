import json
import re
import asyncio
from typing import Optional, List, Dict, Any, Union
from functools import lru_cache
from ..core.config import settings


class SimpleLLMClient:
    """
    Simple HTTP client for OpenRouter API.
    
    Uses lazy client creation with per-request client initialization
    to avoid event loop issues in tests.
    """
    
    def __init__(self):
        self.api_key = settings.openrouter_api_key or ""
        self.base_url = settings.openrouter_base_url
    
    def _get_client(self):
        """Get a fresh httpx client for this request."""
        import httpx
        return httpx.AsyncClient(timeout=settings.timeout)
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a chat completion using OpenRouter."""
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")
        
        model = model or settings.default_model
        temperature = temperature if temperature is not None else settings.temperature
        max_tokens = max_tokens if max_tokens is not None else settings.max_tokens
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://gameapy.app",
            "X-Title": "Gameapy"
        }
        
        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
            **kwargs
        }
        
        client = self._get_client()
        try:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            return response.json()
        finally:
            await client.aclose()
    
    async def close(self):
        """No-op for compatibility (clients are now per-request)."""
        pass


# Global client instance
simple_llm_client = SimpleLLMClient()