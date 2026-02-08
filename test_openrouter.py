# OpenRouter Integration Test
import asyncio
import json
from app.services.simple_llm_fixed import simple_llm_client
from app.core.config import settings

async def test_openrouter_integration():
    """Test OpenRouter integration."""
    
    if not settings.openrouter_api_key:
        print("❌ OpenRouter API key not configured")
        print("Set OPENROUTER_API_KEY in your .env file")
        return
    
    print("🔧 Testing OpenRouter integration...")
    
    try:
        # Test basic chat completion
        messages = [
            {"role": "system", "content": "You are a baseball coach counselor."},
            {"role": "user", "content": "I'm feeling stressed about work. Can you help?"}
        ]
        
        response = await simple_llm_client.chat_completion(
            messages=messages,
            model="anthropic/claude-3-haiku",
            temperature=0.7,
            max_tokens=100
        )
        
        # Extract content
        content = response.get('choices', [{}])[0].get('message', {}).get('content', '')
        
        print("✅ OpenRouter API working!")
        print(f"📝 Response: {content[:100]}...")
        
        # Test with different model
        print("\n🔄 Testing with fallback model...")
        fallback_response = await simple_llm_client.chat_completion(
            messages=messages,
            model="openai/gpt-3.5-turbo",
            temperature=0.7,
            max_tokens=100
        )
        
        fallback_content = fallback_response.get('choices', [{}])[0].get('message', {}).get('content', '')
        print(f"✅ Fallback model working!")
        print(f"📝 Fallback Response: {fallback_content[:100]}...")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Check your API key and internet connection")
    
    finally:
        await simple_llm_client.close()

if __name__ == "__main__":
    asyncio.run(test_openrouter_integration())