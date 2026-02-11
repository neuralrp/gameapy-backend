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
    """Format loaded cards as human-readable context string for LLM."""
    sections = []
    
    if context['self_card']:
        sections.append(_format_self_card_prose(context['self_card']))
    
    if context['pinned_cards']:
        sections.append("## People & Events Kept in Mind")
        for card in context['pinned_cards']:
            sections.append(_format_card_prose(card))
    
    if context['current_mentions']:
        sections.append("## Currently Discussing")
        for card in context['current_mentions']:
            sections.append(_format_card_prose(card))
    
    if context['recent_cards']:
        sections.append("## Recently Referenced")
        for card in context['recent_cards']:
            sections.append(_format_card_prose(card))
    
    return "\n\n".join(sections) if sections else "No context loaded"


def _format_self_card_prose(card: Dict) -> str:
    """Format self card as human-readable prose."""
    payload = card.get('payload', {})
    
    parts = ["## About This User"]
    
    if payload.get('name'):
        parts.append(f"Name: {payload['name']}")
    
    if payload.get('personality'):
        parts.append(f"Personality: {payload['personality']}")
    
    if payload.get('traits'):
        parts.append(f"Traits: {', '.join(payload['traits'][:5])}")
    
    if payload.get('interests'):
        parts.append(f"Interests: {', '.join(payload['interests'][:5])}")
    
    if payload.get('values'):
        parts.append(f"Values: {', '.join(payload['values'][:5])}")
    
    if payload.get('goals'):
        goals = payload['goals'][:3]
        goal_str = '; '.join([g.get('goal', g) if isinstance(g, dict) else g for g in goals])
        parts.append(f"Goals: {goal_str}")
    
    if payload.get('triggers'):
        parts.append(f"Triggers: {', '.join(payload['triggers'][:3])}")
    
    if payload.get('coping_strategies'):
        parts.append(f"Coping: {', '.join(payload['coping_strategies'][:3])}")
    
    return '\n'.join(parts)


def _format_card_prose(card: Dict) -> str:
    """Format character/world card as human-readable prose."""
    card_type = card.get('card_type', '')
    payload = card.get('payload', {})
    
    if card_type == 'character':
        parts = []
        name = payload.get('name', 'Someone')
        parts.append(f"**{name}**")
        
        rel_type = payload.get('relationship_type', 'person')
        parts.append(f"Relationship: {rel_type}")
        
        if payload.get('personality'):
            parts.append(f"Personality: {payload['personality']}")
        
        if payload.get('emotional_state', {}).get('user_to_other'):
            emo = payload['emotional_state']['user_to_other']
            parts.append(
                f"Dynamic — Trust: {emo.get('trust', 'N/A')}/100, "
                f"Conflict: {emo.get('conflict', 'N/A')}/100, "
                f"Bond: {emo.get('emotional_bond', 'N/A')}/100"
            )
        
        if payload.get('key_events'):
            events = payload['key_events'][:2]
            for ev in events:
                parts.append(f"- {ev.get('event', '')} ({ev.get('date', 'unknown')})")
        
        if payload.get('user_feelings'):
            feelings = payload['user_feelings'][:2]
            feeling_str = ', '.join([f['feeling'] for f in feelings])
            parts.append(f"User feels: {feeling_str}")
        
        return '\n'.join(parts)
    
    elif card_type == 'world':
        parts = []
        title = payload.get('title', 'Event')
        event_type = payload.get('event_type', 'event')
        parts.append(f"**{title}** — {event_type}")
        
        if payload.get('description'):
            parts.append(payload['description'][:200])
        
        if payload.get('key_array'):
            parts.append(f"Key themes: {', '.join(payload['key_array'][:5])}")
        
        resolved = payload.get('resolved', False)
        parts.append(f"Status: {'resolved' if resolved else 'ongoing'}")
        
        return '\n'.join(parts)
    
    return f"{card_type.upper()}: {card.get('name', card.get('title', 'Card'))}"


def _format_counselor_examples(examples: List[Dict]) -> str:
    """Format session examples for system prompt."""
    if not examples:
        return ""
    
    example = examples[0]
    return (
        f"User: {example['user_situation']}\n"
        f"You: {example['your_response']}\n"
        f"Approach: {example['approach']}\n"
    )


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
    crisis_protocol = counselor_data.get('crisis_protocol', '')
    
    prompt += f"You are {name}. {who_you_are}\n\n"
    
    if your_vibe:
        prompt += f"Your vibe: {your_vibe}\n\n"
    
    if your_worldview:
        prompt += f"Your worldview: {your_worldview}\n\n"
    
    if session_template:
        prompt += f"Session opening: {session_template}\n\n"
    
    if examples:
        prompt += "Example of your approach:\n"
        prompt += _format_counselor_examples(examples)
        prompt += "\n"
    
    if crisis_protocol:
        prompt += "If user expresses self-harm or crisis: prioritize safety, validate courage, and provide resources: "
        prompt += "**988** (call/text), **Crisis Text Line** (text HOME to 741741). Stay present until safety plan established.\n"
    
    return prompt


@router.post("/chat")
async def chat_with_counselor(request: ChatRequest):
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
        
        # 2. Get counselor profile from session
        counselor_id = session.get('counselor_id')
        if not counselor_id:
            raise HTTPException(status_code=400, detail="Session has no counselor assigned")
        
        counselor = db.get_counselor_profile(counselor_id)
        if not counselor:
            raise HTTPException(status_code=404, detail=f"Counselor profile not found (id={counselor_id})")
        
        counselor_data = counselor['profile']['data']
        
        # Easter Egg: "Summon Deirdre" (case-insensitive)
        counselor_switched = False
        new_counselor_data = None
        if message_data.content.lower().strip() == "summon deirdre" and counselor_data['name'].lower() == "marina":
            deirdre_counselor = db.get_counselor_by_name("Deirdre")
            if deirdre_counselor:
                db.update_session_counselor(session_id, deirdre_counselor['id'])
                counselor_switched = True
                new_counselor_data = deirdre_counselor['profile']['data']
                counselor = deirdre_counselor
                counselor_id = deirdre_counselor['id']
                counselor_data = new_counselor_data
        
        # 3. Assemble context for LLM
        context = context_assembler.assemble_context(
            client_id=client_id,
            session_id=session_id,
            user_message=message_data.content
        )
        
        # 4. Get session messages for conversation history
        session_messages = db.get_session_messages(session_id, limit=10)
        
        # 5. Format context for LLM
        context_str = _format_context_for_llm(context)
        
        # 6. Build system prompt from counselor data
        system_prompt_content = _build_counselor_system_prompt(counselor_data)
        
        # Add context as system message
        llm_messages = [
            {"role": "system", "content": f"{system_prompt_content}\n\n---\n\nContext about this user:\n{context_str}"}
        ]
        
        # Convert DB messages to LLM format
        for msg in session_messages:
            role = "assistant" if msg['speaker'] == 'counselor' else "user"
            llm_messages.append({
                "role": role,
                "content": msg['content']
            })
        
        from fastapi.responses import StreamingResponse
        
        async def generate():
            """Generate streaming response."""
            full_response = ""
            
            try:
                # Stream LLM response
                async for chunk in simple_llm_client.chat_completion_stream(
                    messages=llm_messages,
                    temperature=0.7,
                    max_tokens=2000
                ):
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        full_response += content
                        # Send content chunk
                        yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"
                
                # Store full response in database
                ai_message_id = None
                if full_response:
                    ai_message_id = db.add_message(
                        session_id=session_id,
                        role="assistant",
                        content=full_response,
                        speaker="counselor"
                    )
                
                # Send final metadata chunk
                metadata = {
                    'type': 'done',
                    'data': {
                        'cards_loaded': context.get('total_cards_loaded', 0),
                        'counselor_switched': counselor_switched,
                        'new_counselor': new_counselor_data if counselor_switched else None
                    }
                }
                yield f"data: {json.dumps(metadata)}\n\n"
            except Exception as e:
                # Send error as final chunk
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
        
    except HTTPException:
        raise
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