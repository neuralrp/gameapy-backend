import httpx
import json
import asyncio
from typing import Dict, List, Any, Optional, AsyncGenerator
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from ..core.config import settings


class OpenRouterClient:
    """Thin wrapper around OpenAI client for OpenRouter API."""
    
    def __init__(self, api_key: str = None, base_url: str = None):
        """Initialize OpenRouter client."""
        self.api_key = api_key or settings.openrouter_api_key or ""
        self.base_url = base_url or settings.openrouter_base_url
        
        # Create AsyncOpenAI client with OpenRouter settings
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=settings.timeout
        )
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
        stream: bool = False,
        **kwargs
    ) -> ChatCompletion:
        """
        Create a chat completion using OpenRouter.
        
        Args:
            messages: List of message dicts with role and content
            model: Model to use (defaults to settings.default_model)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            **kwargs: Additional parameters
            
        Returns:
            ChatCompletion object
        """
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")
        
        model = model or settings.default_model
        temperature = temperature if temperature is not None else settings.temperature
        max_tokens = max_tokens if max_tokens is not None else settings.max_tokens
        
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                **kwargs
            )
            return response
        except Exception as e:
            # Try fallback model if primary fails
            if model != settings.fallback_model:
                return await self.chat_completion(
                    messages=messages,
                    model=settings.fallback_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=stream,
                    **kwargs
                )
            raise e
    
    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
        **kwargs
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """
        Stream a chat completion using OpenRouter.
        
        Args:
            messages: List of message dicts with role and content
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Yields:
            ChatCompletionChunk objects
        """
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")
        
        model = model or settings.default_model
        temperature = temperature if temperature is not None else settings.temperature
        max_tokens = max_tokens or settings.max_tokens
        
        try:
            stream = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs
            )
            
            async for chunk in stream:
                yield chunk
                
        except Exception as e:
            # Try fallback model if primary fails
            if model != settings.fallback_model:
                async for chunk in self.chat_completion_stream(
                    messages=messages,
                    model=settings.fallback_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                ):
                    yield chunk
            else:
                raise e
    
    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models from OpenRouter."""
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            response.raise_for_status()
            return response.json().get("data", [])
    
    def get_model_info(self, model: str) -> Dict[str, Any]:
        """Get information about a specific model."""
        # Common model configurations
        model_configs = {
            "anthropic/claude-3-haiku": {
                "name": "Claude 3 Haiku",
                "provider": "Anthropic",
                "context_length": 200000,
                "pricing": "$0.25/1M input, $1.25/1M output",
                "speed": "fast",
                "quality": "high"
            },
            "anthropic/claude-3-sonnet": {
                "name": "Claude 3 Sonnet", 
                "provider": "Anthropic",
                "context_length": 200000,
                "pricing": "$3/1M input, $15/1M output",
                "speed": "medium",
                "quality": "very_high"
            },
            "openai/gpt-3.5-turbo": {
                "name": "GPT-3.5 Turbo",
                "provider": "OpenAI",
                "context_length": 16385,
                "pricing": "$0.50/1M input, $1.50/1M output",
                "speed": "fast",
                "quality": "medium"
            },
            "openai/gpt-4": {
                "name": "GPT-4",
                "provider": "OpenAI", 
                "context_length": 8192,
                "pricing": "$30/1M input, $60/1M output",
                "speed": "slow",
                "quality": "high"
            },
            "meta-llama/llama-3-8b-instruct": {
                "name": "Llama 3 8B Instruct",
                "provider": "Meta",
                "context_length": 8192,
                "pricing": "$0.10/1M input, $0.10/1M output",
                "speed": "fast",
                "quality": "medium"
            }
        }
        
        return model_configs.get(model, {
            "name": model,
            "provider": "Unknown",
            "context_length": "Unknown",
            "pricing": "Unknown",
            "speed": "Unknown",
            "quality": "Unknown"
        })


# Global client instance
openrouter_client = OpenRouterClient()