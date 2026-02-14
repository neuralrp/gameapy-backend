from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
import json
import asyncio

from app.models.schemas import (
    MessageCreate, APIResponse, ChatRequest
)
from app.db.database import db
from app.services.simple_llm_fixed import simple_llm_client
from app.services.insight_extractor import insight_extractor
from app.services.entity_detector import entity_detector
from app.services.context_assembler import context_assembler
from app.services.friendship_analyzer import friendship_analyzer
from app.core.config import settings
from app.config.core_truths import get_core_truths
from app.utils.card_metadata import CardMetadata
from app.auth import get_current_user

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
    """Format self card as human-readable prose with recency indicators."""
    payload = card.get('payload', {})
    
    metadata = CardMetadata(payload) if '_metadata' in payload else None
    
    parts = ["## About This User"]
    
    if payload.get('name'):
        name = payload['name']
        recency = f" {metadata.get_recency_indicator('name')}" if metadata else ""
        parts.append(f"Name: {name}{recency}")
    
    if payload.get('personality'):
        personality = payload['personality']
        recency = f" {metadata.get_recency_indicator('personality')}" if metadata else ""
        parts.append(f"Personality: {personality}{recency}")
    
    if payload.get('traits'):
        traits = ', '.join(payload['traits'][:5])
        recency = f" {metadata.get_recency_indicator('traits')}" if metadata else ""
        parts.append(f"Traits: {traits}{recency}")
    
    if payload.get('interests'):
        interests = ', '.join(payload['interests'][:5])
        recency = f" {metadata.get_recency_indicator('interests')}" if metadata else ""
        parts.append(f"Interests: {interests}{recency}")
    
    if payload.get('values'):
        values = ', '.join(payload['values'][:5])
        recency = f" {metadata.get_recency_indicator('values')}" if metadata else ""
        parts.append(f"Values: {values}{recency}")
    
    if payload.get('goals'):
        goals = payload['goals'][:3]
        goal_str = '; '.join([g.get('goal', g) if isinstance(g, dict) else g for g in goals])
        recency = f" {metadata.get_recency_indicator('goals')}" if metadata else ""
        parts.append(f"Goals: {goal_str}{recency}")
    
    if payload.get('triggers'):
        triggers = ', '.join(payload['triggers'][:3])
        recency = f" {metadata.get_recency_indicator('triggers')}" if metadata else ""
        parts.append(f"Triggers: {triggers}{recency}")
    
    if payload.get('coping_strategies'):
        coping = ', '.join(payload['coping_strategies'][:3])
        recency = f" {metadata.get_recency_indicator('coping_strategies')}" if metadata else ""
        parts.append(f"Coping: {coping}{recency}")
    
    return '\n'.join(parts)


def _format_card_prose(card: Dict) -> str:
    """Format character/world card as human-readable prose with recency indicators."""
    card_type = card.get('card_type', '')
    payload = card.get('payload', {})
    
    metadata = CardMetadata(payload) if '_metadata' in payload else None
    
    if card_type == 'character':
        parts = []
        name = payload.get('name', 'Someone')
        name_recency = f" {metadata.get_recency_indicator('name')}" if metadata else ""
        parts.append(f"**{name}**{name_recency}")
        
        rel_type = payload.get('relationship_type', 'person')
        rel_recency = f" {metadata.get_recency_indicator('relationship_type')}" if metadata else ""
        parts.append(f"Relationship: {rel_type}{rel_recency}")
        
        if payload.get('personality'):
            personality = payload['personality']
            personality_recency = f" {metadata.get_recency_indicator('personality')}" if metadata else ""
            parts.append(f"Personality: {personality}{personality_recency}")
        
        if payload.get('emotional_state', {}).get('user_to_other'):
            emo = payload['emotional_state']['user_to_other']
            emo_recency = f" {metadata.get_recency_indicator('emotional_state.user_to_other')}" if metadata else ""
            parts.append(
                f"Dynamic — Trust: {emo.get('trust', 'N/A')}/100, "
                f"Conflict: {emo.get('conflict', 'N/A')}/100, "
                f"Bond: {emo.get('emotional_bond', 'N/A')}/100{emo_recency}"
            )
        
        if payload.get('key_events'):
            events = payload['key_events'][:2]
            events_recency = f" {metadata.get_recency_indicator('key_events')}" if metadata else ""
            for ev in events:
                parts.append(f"- {ev.get('event', '')} ({ev.get('date', 'unknown')})")
            if events_recency:
                parts[-1] += events_recency
        
        if payload.get('user_feelings'):
            feelings = payload['user_feelings'][:2]
            feeling_str = ', '.join([f['feeling'] for f in feelings])
            feelings_recency = f" {metadata.get_recency_indicator('user_feelings')}" if metadata else ""
            parts.append(f"User feels: {feeling_str}{feelings_recency}")
        
        return '\n'.join(parts)
    
    elif card_type == 'world':
        parts = []
        title = payload.get('title', 'Event')
        event_type = payload.get('event_type', 'event')
        title_recency = f" {metadata.get_recency_indicator('title')}" if metadata else ""
        parts.append(f"**{title}** — {event_type}{title_recency}")
        
        if payload.get('description'):
            description = payload['description'][:200]
            desc_recency = f" {metadata.get_recency_indicator('description')}" if metadata else ""
            parts.append(f"{description}{desc_recency}")
        
        if payload.get('key_array'):
            themes = ', '.join(payload['key_array'][:5])
            themes_recency = f" {metadata.get_recency_indicator('key_array')}" if metadata else ""
            parts.append(f"Key themes: {themes}{themes_recency}")
        
        resolved = payload.get('resolved', False)
        resolved_recency = f" {metadata.get_recency_indicator('resolved')}" if metadata else ""
        parts.append(f"Status: {'resolved' if resolved else 'ongoing'}{resolved_recency}")
        
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


def _build_counselor_system_prompt(counselor_data: Dict, client_id: int = 0, counselor_id: int = 0) -> str:
    """Build system prompt from counselor profile data with friendship context."""
    prompt = get_core_truths()
    prompt += "\n\n---\n\n"
    
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
    
    if client_id and counselor_id:
        friendship = db.get_friendship_level(client_id, counselor_id)
        db.update_last_interaction(client_id, counselor_id)
        friendship_prompt = friendship_analyzer.get_friendship_prompt(friendship['level'])
        prompt += friendship_prompt
        prompt += "\n\n"
    
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
async def chat_with_counselor(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Stream chat response from counselor.
    Uses authenticated user's ID from JWT.
    """
    try:
        client_id = current_user["id"]
        session_id = request.session_id
        message_data = request.message_data
        
        session = db.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if session['client_id'] != client_id:
            raise HTTPException(status_code=403, detail="Access denied to this session")
        
        user_message_id = db.add_message(
            session_id=session_id,
            role=message_data.role,
            content=message_data.content,
            speaker="client"
        )
        
        db.increment_message_counter(client_id)
        
        mentions = entity_detector.detect_mentions(message_data.content, client_id)
        for mention in mentions:
            db.add_entity_mention(
                client_id=client_id,
                session_id=session_id,
                entity_type=f"{mention['card_type']}_card",
                entity_ref=str(mention['card_id']),
                mention_context=message_data.content
            )
        
        counselor_id = session.get('counselor_id')
        if not counselor_id:
            raise HTTPException(status_code=400, detail="Session has no counselor assigned")
        
        counselor = db.get_counselor_profile(counselor_id)
        if not counselor:
            raise HTTPException(status_code=404, detail=f"Counselor profile not found (id={counselor_id})")
        
        counselor_data = counselor['profile']['data']
        
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
        
        context = context_assembler.assemble_context(
            client_id=client_id,
            session_id=session_id,
            user_message=message_data.content
        )
        
        session_messages = db.get_session_messages(session_id, limit=10)
        
        context_str = _format_context_for_llm(context)
        
        system_prompt_content = _build_counselor_system_prompt(
            counselor_data, 
            client_id=client_id, 
            counselor_id=counselor_id
        )
        
        llm_messages = [
            {"role": "system", "content": f"{system_prompt_content}\n\n---\n\nContext about this user:\n{context_str}"}
        ]
        
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
                async for chunk in simple_llm_client.chat_completion_stream(
                    messages=llm_messages,
                    temperature=0.7,
                    max_tokens=2000
                ):
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        full_response += content
                        yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"
                
                ai_message_id = None
                if full_response:
                    ai_message_id = db.add_message(
                        session_id=session_id,
                        role="assistant",
                        content=full_response,
                        speaker="counselor"
                    )
                
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
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/insights/extract", response_model=APIResponse)
async def extract_insights(
    session_id: int,
    dimensions: List[str] = ["engagement", "mood", "insight"],
    current_user: dict = Depends(get_current_user)
):
    """
    Extract insights from a counseling session.
    """
    try:
        session = db.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if session['client_id'] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        
        session_messages = db.get_session_messages(session_id)
        
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
