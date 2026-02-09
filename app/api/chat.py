from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
import json
import asyncio

from app.models.schemas import (
    ClientProfile, CounselorProfile, Message, MessageCreate,
    SessionCreate, SessionWithMessages, APIResponse, ChatRequest,
    CharacterCard, CharacterCardCreate,
    GameState, FarmItem, FarmItemCreate, FarmShopResponse,
    ShopItem, HealthResponse
)
from app.db.database import db
from app.services.simple_llm_fixed import simple_llm_client
from app.services.insight_extractor import insight_extractor
from app.services.entity_detector import entity_detector
from app.services.context_assembler import context_assembler
from app.core.config import settings
from app.config.core_truths import get_core_truths

router = APIRouter()


def _format_context_for_llm(context: Dict) -> str:
    """Format loaded cards as context string for LLM."""
    sections = []
    
    if context['self_card']:
        sections.append(f"### Self Card\n{json.dumps(context['self_card'], indent=2)}")
    
    if context['pinned_cards']:
        sections.append(f"### Pinned Cards ({len(context['pinned_cards'])})")
        for card in context['pinned_cards']:
            name = card.get('name', card.get('title', f'Card {card["id"]}'))
            sections.append(f"- {card['card_type'].upper()}: {name}")
    
    if context['current_mentions']:
        sections.append(f"### Current Session Mentions ({len(context['current_mentions'])})")
        for card in context['current_mentions']:
            name = card.get('name', card.get('title', f'Card {card["id"]}'))
            sections.append(f"- {card['card_type'].upper()}: {name}")
    
    if context['recent_cards']:
        sections.append(f"### Recent Cards ({len(context['recent_cards'])})")
        for card in context['recent_cards']:
            name = card.get('name', card.get('title', f'Card {card["id"]}'))
            sections.append(f"- {card['card_type'].upper()}: {name}")
    
    return "\n\n".join(sections) if sections else "No context loaded"


def _format_counselor_examples(examples: List[Dict]) -> str:
    """Format session examples for system prompt."""
    formatted = []
    for example in examples:
        formatted.append(f"User: {example['user_situation']}")
        formatted.append(f"You: {example['your_response']}")
        formatted.append(f"Approach: {example['approach']}\n")
    return "\n".join(formatted)


def _build_counselor_system_prompt(counselor_data: Dict) -> str:
    """Build system prompt from counselor profile data."""
    # Start with universal core truths
    prompt = get_core_truths()
    prompt += "\n\n---\n\n"
    
    # Add persona-specific identity
    name = counselor_data['name']
    who_you_are = counselor_data.get('who_you_are', '')
    your_vibe = counselor_data.get('your_vibe', '')
    your_worldview = counselor_data.get('your_worldview', '')
    session_template = counselor_data.get('session_template', '')
    examples = counselor_data.get('session_examples', [])
    tags = counselor_data.get('tags', [])
    crisis_protocol = counselor_data.get('crisis_protocol', '')
    
    prompt += f"You are {name}. {who_you_are}\n\n"
    
    if your_vibe:
        prompt += f"Your vibe: {your_vibe}\n\n"
    
    if your_worldview:
        prompt += f"Your worldview: {your_worldview}\n\n"
    
    if session_template:
        prompt += f"Session opening: {session_template}\n\n"
    
    if examples:
        prompt += "Examples of your approach:\n"
        prompt += _format_counselor_examples(examples)
        prompt += "\n"
    
    if tags:
        prompt += f"Tags: {', '.join(tags)}\n\n"
    
    if crisis_protocol:
        prompt += f"\nCrisis protocol:\n{crisis_protocol}\n"
    
    return prompt


@router.post("/chat", response_model=APIResponse)
async def chat_with_counselor(request: ChatRequest):
    """
    Chat with a counselor character and get AI response.
    """
    try:
        session_id = request.session_id
        message_data = request.message_data
        # Get session details
        session = db.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        client_id = session['client_id']
        
        # Add user message to session
        user_message_id = db.add_message(
            session_id=session_id,
            role=message_data.role,
            content=message_data.content,
            speaker="client"
        )
        
        # 1. Detect and log entity mentions
        mentions = entity_detector.detect_mentions(message_data.content, client_id)
        for mention in mentions:
            db.add_entity_mention(
                client_id=client_id,
                session_id=session_id,
                entity_type=f"{mention['card_type']}_card",
                entity_ref=str(mention['card_id']),
                mention_context=message_data.content
            )
        
        # 2. Assemble context for LLM
        context = context_assembler.assemble_context(
            client_id=client_id,
            session_id=session_id,
            user_message=message_data.content
        )
        
        # 3. Get session messages for conversation history
        session_messages = db.get_session_messages(session_id, limit=10)
        
        # Get counselor profile from session
        counselor_id = session.get('counselor_id')
        if not counselor_id:
            raise HTTPException(status_code=400, detail="Session has no counselor assigned")
        
        counselor = db.get_counselor_profile(counselor_id)
        if not counselor:
            raise HTTPException(status_code=404, detail=f"Counselor profile not found (id={counselor_id})")
        
        counselor_data = json.loads(counselor['profile_json'])['data']
        
        # 4. Format context for LLM
        context_str = _format_context_for_llm(context)
        
        # 5. Build system prompt from counselor data
        system_prompt_content = _build_counselor_system_prompt(counselor_data)
        
        # Add context as system message
        llm_messages = [
            {"role": "system", "content": f"Context:\n{context_str}\n\n{system_prompt_content}"}
        ]
        
        # Convert DB messages to LLM format
        for msg in session_messages:
            role = "assistant" if msg['speaker'] == 'counselor' else "user"
            llm_messages.append({
                "role": role,
                "content": msg['content']
            })
        
        # 6. Get AI response
        response = await simple_llm_client.chat_completion(
            messages=llm_messages,
            temperature=0.7,
            max_tokens=150
        )
        
        ai_content = response.get('choices', [{}])[0].get('message', {}).get('content', '')
        
        # Add AI response to session
        if ai_content:
            ai_message_id = db.add_message(
                session_id=session_id,
                role="assistant",
                content=ai_content,
                speaker="counselor"
            )
        else:
            ai_message_id = None
        
        return APIResponse(
            success=True,
            message="Message processed successfully",
            data={
                "user_message_id": user_message_id,
                "ai_message_id": ai_message_id,
                "ai_response": ai_content or "",
                "cards_loaded": context.get('total_cards_loaded', 0)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_with_counselor_stream(request: ChatRequest):
    """
    Stream chat response from counselor.
    """
    try:
        session_id = request.session_id
        message_data = request.message_data
        # Get session details first
        session = db.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Add user message to session
        user_message_id = db.add_message(
            session_id=session_id,
            role=message_data.role,
            content=message_data.content,
            speaker="client"
        )
        
        # Get session details
        session_messages = db.get_session_messages(session_id, limit=10)
        
        # Get counselor profile from session
        counselor_id = session.get('counselor_id')
        if not counselor_id:
            raise HTTPException(status_code=400, detail="Session has no counselor assigned")
        
        counselor = db.get_counselor_profile(counselor_id)
        if not counselor:
            raise HTTPException(status_code=404, detail=f"Counselor profile not found (id={counselor_id})")
        
        counselor_data = json.loads(counselor['profile_json'])['data']
        
        # Build system prompt from counselor data
        system_prompt_content = _build_counselor_system_prompt(counselor_data)
        
        # Convert DB messages to LLM format
        llm_messages = [{"role": "system", "content": system_prompt_content}]
        for msg in session_messages:
            role = "assistant" if msg['speaker'] == 'counselor' else "user"
            llm_messages.append({
                "role": role,
                "content": msg['content']
            })
        
        from fastapi.responses import StreamingResponse
        
        async def generate():
            full_response = ""
            # For now, use non-streaming for simplicity
            response = await simple_llm_client.chat_completion(
                messages=llm_messages,
                temperature=0.7,
                max_tokens=150
            )
            
            full_response = response.get('choices', [{}])[0].get('message', {}).get('content', '')
            yield f"data: {json.dumps({'content': full_response})}\n\n"
        
        # Store the response in database
        full_response = ""
        response = await simple_llm_client.chat_completion(
            messages=llm_messages,
            temperature=0.7,
            max_tokens=150
        )
        
        full_response = response.get('choices', [{}])[0].get('message', {}).get('content', '')
        
        if full_response:
            ai_message_id = db.add_message(
                session_id=session_id,
                role="assistant", 
                content=full_response,
                speaker="counselor"
            )
        else:
            ai_message_id = None
        
        return StreamingResponse(
            generate(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/insights/extract", response_model=APIResponse)
async def extract_insights(
    session_id: int,
    dimensions: List[str] = ["engagement", "mood", "insight"]
):
    """
    Extract insights from a counseling session.
    """
    try:
        # Get session details
        session_messages = db.get_session_messages(session_id)
        
        # Get client profile (simplified)
        client_profile = {
            "spec": "client_profile_v1",
            "data": {
                "name": "Alex",
                "personality": "Analytical, perfectionist",
                "goals": ["manage stress", "improve communication"],
                "presenting_issues": [
                    {"issue": "workplace anxiety", "severity": "moderate"}
                ]
            }
        }
        
        # Extract insights
        insights = await insight_extractor.extract_session_insights(
            messages=session_messages,
            client_profile=client_profile,
            dimensions=dimensions,
            session_metadata={"session_number": 1}
        )
        
        if not insights:
            raise HTTPException(status_code=500, detail="Failed to extract insights")
        
        return APIResponse(
            success=True,
            message="Insights extracted successfully",
            data=insights
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models", response_model=APIResponse)
async def get_available_models():
    """Get list of available LLM models from OpenRouter."""
    try:
        # Return predefined models for now
        models = [
            {"id": "anthropic/claude-3-haiku", "name": "Claude 3 Haiku"},
            {"id": "openai/gpt-3.5-turbo", "name": "GPT-3.5 Turbo"},
            {"id": "meta-llama/llama-3-8b-instruct", "name": "Llama 3 8B"}
        ]
        
        return APIResponse(
            success=True,
            message="Models retrieved successfully",
            data=models
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/{model_id}", response_model=APIResponse)
async def get_model_info(model_id: str):
    """Get information about a specific model."""
    try:
        # Return predefined model info
        model_configs = {
            "anthropic/claude-3-haiku": {
                "name": "Claude 3 Haiku",
                "provider": "Anthropic",
                "context_length": 200000,
                "pricing": "$0.25/1M input, $1.25/1M output",
                "speed": "fast",
                "quality": "high"
            },
            "openai/gpt-3.5-turbo": {
                "name": "GPT-3.5 Turbo",
                "provider": "OpenAI",
                "context_length": 16385,
                "pricing": "$0.50/1M input, $1.50/1M output",
                "speed": "fast",
                "quality": "medium"
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
        
        model_info = model_configs.get(model_id, {
            "name": model_id,
            "provider": "Unknown",
            "context_length": "Unknown",
            "pricing": "Unknown",
            "speed": "Unknown",
            "quality": "Unknown"
        })
        
        return APIResponse(
            success=True,
            message="Model info retrieved successfully",
            data=model_info
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))