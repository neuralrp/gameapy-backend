import json
import re
import asyncio
from typing import Optional, List, Dict, Any, Union
from functools import lru_cache
from ..core.config import settings


class SimpleLLMClient:
    """
    Simple HTTP client for OpenRouter API.
    """
    
    def __init__(self):
        import httpx
        self.api_key = settings.openrouter_api_key
        self.base_url = settings.openrouter_base_url
        self.client = httpx.AsyncClient(timeout=settings.timeout)
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
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
        
        response = await self.client.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Global client instance
simple_llm_client = SimpleLLMClient()