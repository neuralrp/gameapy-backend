import pytest
import asyncio
import os
from app.services.simple_llm import simple_llm_client
from app.core.config import settings

# Skip tests if no API key
pytestmark = pytest.mark.skipif(
    not settings.openrouter_api_key,
    reason="OpenRouter API key not configured"
)


@pytest.mark.asyncio
async def test_simple_llm_client():
    """Test the simple LLM client."""
    
    # Test basic chat completion
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is 2+2?"}
    ]
    
    response = await simple_llm_client.chat_completion(
        messages=messages,
        temperature=0.1,
        max_tokens=50
    )
    
    # Verify response structure
    assert "choices" in response
    assert len(response["choices"]) > 0
    assert "message" in response["choices"][0]
    assert "content" in response["choices"][0]["message"]
    
    # Verify content is reasonable
    content = response["choices"][0]["message"]["content"]
    assert "4" in content or "four" in content.lower()


@pytest.mark.asyncio
async def test_chat_with_counselor(test_client):
    """Test chat endpoint through FastAPI."""
    
    # Create a session first
    session_response = test_client.post(
        "/api/v1/sessions",
        json={"client_id": 1, "counselor_id": 1}
    )
    session_data = session_response.json()
    session_id = session_data["data"]["session_id"]
    
    # Send a message
    response = test_client.post(
        f"/api/v1/chat/chat?session_id={session_id}",
        json={
            "role": "user",
            "content": "I'm feeling stressed about work"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "ai_response" in data["data"]
    assert len(data["data"]["ai_response"]) > 0


@pytest.mark.asyncio
async def test_insight_extraction(test_client):
    """Test insight extraction endpoint."""
    
    # Create a session first
    session_response = test_client.post(
        "/api/v1/sessions",
        json={"client_id": 1, "counselor_id": 1}
    )
    session_data = session_response.json()
    session_id = session_data["data"]["session_id"]
    
    # Add some messages
    messages = [
        {"role": "user", "content": "I'm feeling anxious about work"},
        {"role": "assistant", "content": "Tell me more about what's causing the anxiety"},
        {"role": "user", "content": "My boss is really demanding and I feel overwhelmed"}
    ]
    
    for msg in messages:
        test_client.post(
            f"/api/v1/messages?session_id={session_id}",
            json=msg
        )
    
    # Extract insights
    response = test_client.post(
        f"/api/v1/chat/insights/extract?session_id={session_id}",
        json=["engagement", "mood", "insight"]
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "dimensions" in data["data"]
    assert "session_summary" in data["data"]