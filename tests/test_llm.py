import pytest
import asyncio
import os
from app.services.simple_llm import simple_llm_client
from app.core.config import settings
import json

def parse_sse_response(response_text: str) -> list:
    """
    Parse SSE (Server-Sent Events) streaming response into list of chunks.
    
    Args:
        response_text: Raw response text from streaming endpoint
        
    Returns:
        List of parsed chunk dictionaries
    """
    chunks = []
    for line in response_text.split('\n\n'):
        line = line.strip()
        if line.startswith('data: '):
            try:
                chunk = json.loads(line[6:])
                chunks.append(chunk)
            except (json.JSONDecodeError, ValueError):
                pass
    return chunks

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
async def test_chat_with_counselor(test_client_with_auth, sample_user, sample_counselor, mock_llm_success):
    """Test chat endpoint through FastAPI."""

    session_id = None
    from app.db.database import db
    session_id = db.create_session(
        client_id=sample_user,
        counselor_id=sample_counselor
    )

    response = test_client_with_auth.post(
        f"/api/v1/chat/chat",
        json={
            "session_id": session_id,
            "message_data": {
                "role": "user",
                "content": "I'm feeling stressed about work"
            }
        }
    )

    assert response.status_code == 200
    chunks = parse_sse_response(response.text)
    assert chunks[-1]['type'] == 'done'
    assert chunks[-1]['data']['cards_loaded'] >= 0


@pytest.mark.asyncio
async def test_insight_extraction(test_client_with_auth, sample_user, sample_counselor):
    """Test insight extraction endpoint."""

    from app.db.database import db
    session_id = db.create_session(
        client_id=sample_user,
        counselor_id=sample_counselor
    )
    
    messages = [
        {"role": "user", "content": "I'm feeling anxious about work"},
        {"role": "assistant", "content": "Tell me more about what's causing the anxiety"},
        {"role": "user", "content": "My boss is really demanding and I feel overwhelmed"}
    ]
    
    for msg in messages:
        db.add_message(
            session_id=session_id,
            role=msg["role"],
            content=msg["content"],
            speaker="client" if msg["role"] == "user" else "counselor"
        )
    
    response = test_client_with_auth.post(
        f"/api/v1/chat/insights/extract?session_id={session_id}",
        json=["engagement", "mood", "insight"]
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "dimensions" in data["data"]
    assert "session_summary" in data["data"]