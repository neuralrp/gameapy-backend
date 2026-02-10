import json
import uuid
from typing import Dict, Any, List, Optional
from ..core.config import settings
from ..services.simple_llm_fixed import simple_llm_client
from ..services.card_generator import card_generator
from ..db.database import db


class GuideSystem:
    """
    Organic conversation system for Gameapy onboarding.
    
    No forced phases - follows user's lead, suggests card creation when appropriate.
    """
    
    def __init__(self):
        self.default_model = settings.default_model or "openrouter/free"
    
    async def start_conversation(self, client_id: int) -> Dict[str, Any]:
        """
        Start organic guide conversation.
        
        Returns:
            {
                "guide_message": str,
                "session_id": int,
                "client_id": int
            }
        """
        guide_counselor_id = self._get_guide_counselor_id()
        session_id = db.create_session(
            client_id=client_id,
            counselor_id=guide_counselor_id
        )
        
        welcome = (
            "Hey there! I'm here to get to know you. "
            "Tell me about yourself - whatever feels important right now."
        )
        
        db.add_message(
            session_id=session_id,
            role="assistant",
            content=welcome,
            speaker="guide"
        )
        
        return {
            "guide_message": welcome,
            "session_id": session_id,
            "client_id": client_id
        }
    
    async def process_conversation(
        self,
        session_id: int,
        user_input: str
    ) -> Dict[str, Any]:
        """
        Process user input in organic conversation.
        
        Detects card-worthy topics and suggests creation with user consent.
        
        Returns:
            {
                "guide_message": str,
                "suggested_card": Optional[Dict],
                "conversation_complete": bool
            }
        """
        session = db.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        client_id = session['client_id']
        
        # Save user message
        db.add_message(
            session_id=session_id,
            role="user",
            content=user_input,
            speaker="client"
        )
        
        # Detect if this reveals a card-worthy topic
        suggested_card = await self._detect_card_worthy_topic(session_id)
        
        if suggested_card:
            # Ask permission to create card
            suggestion_text = self._format_card_suggestion(suggested_card)
            
            db.add_message(
                session_id=session_id,
                role="assistant",
                content=suggestion_text,
                speaker="guide"
            )
            
            return {
                "guide_message": suggestion_text,
                "suggested_card": suggested_card,
                "conversation_complete": False
            }
        else:
            # Continue natural conversation
            response = await self._generate_natural_response(session_id, user_input)
            
            db.add_message(
                session_id=session_id,
                role="assistant",
                content=response,
                speaker="guide"
            )
            
            # Check for farm discovery opportunity
            await self._maybe_suggest_farm(session_id, client_id)
            
            return {
                "guide_message": response,
                "suggested_card": None,
                "conversation_complete": False
            }
    
    async def confirm_card_creation(
        self,
        session_id: int,
        card_type: str,
        topic: str
    ) -> Dict[str, Any]:
        """
        Create card after user confirmation.
        
        Returns:
            {
                "card_id": int,
                "card_data": Dict,
                "guide_message": str
            }
        """
        session = db.get_session(session_id)
        client_id = session['client_id']
        
        # Generate card from topic
        result = await card_generator.generate_card(
            card_type=card_type,
            plain_text=topic,
            context=f"Guide conversation, session {session_id}"
        )
        
        if "generated_card" not in result:
            raise Exception(f"Card generation failed: {result}")
        
        card_data = result["generated_card"]
        
        # Create card based on type
        if card_type == "self":
            card_id = db.create_self_card(
                client_id=client_id,
                card_json=json.dumps(card_data),
                auto_update_enabled=True
            )
            card_name = "Self"
        elif card_type == "character":
            char_data = card_data["data"]
            card_id = db.create_character_card(
                client_id=client_id,
                card_name=char_data["name"],
                relationship_type=char_data["relationship_type"],
                relationship_label=char_data.get("relationship_label"),
                card_data=char_data
            )
            card_name = char_data["name"]
        elif card_type == "world":
            card_id = db.create_world_event(
                client_id=client_id,
                entity_id=f"world_{uuid.uuid4().hex}",
                title=card_data["title"],
                key_array=json.dumps(card_data["key_array"]),
                description=card_data["description"],
                event_type=card_data["event_type"],
                is_canon_law=False,
                auto_update_enabled=True,
                resolved=card_data.get("resolved", False)
            )
            card_name = card_data["title"]
        else:
            raise ValueError(f"Invalid card_type: {card_type}")
        
        # Confirm to user
        message = f"Got it! I've created a card for {card_name}. Anything else you'd like to share?"
        
        db.add_message(
            session_id=session_id,
            role="assistant",
            content=message,
            speaker="guide"
        )
        
        return {
            "card_id": card_id,
            "card_data": card_data,
            "guide_message": message
        }
    
    async def _detect_card_worthy_topic(
        self,
        session_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Detect if conversation reveals card-worthy topic.
        
        Returns:
            None or {
                "card_type": "self|character|world",
                "topic": "description of what to capture",
                "confidence": float
            }
        """
        transcript = self._get_session_transcript(session_id)
        existing_cards = self._get_existing_cards_summary(session_id)
        
        prompt = f"""Analyze this conversation. Has the user mentioned anything worth creating a card for?

TRANSCRIPT:
{transcript}

EXISTING CARDS:
{existing_cards}

Card types:
- self: User's personality, traits, interests, goals, challenges
- character: People in user's life (family, friends, coworkers)
- world: Important moments, achievements, challenges, transitions

Return JSON. If user mentioned something NEW not in existing cards:
{{"card_type": "self|character|world", "topic": "brief description", "confidence": 0.0-1.0}}

If nothing new or confidence low (< 0.6):
{{"card_type": null, "topic": null, "confidence": 0.0}}

Output ONLY JSON."""
        
        try:
            response = await simple_llm_client.chat_completion(
                messages=[{"role": "system", "content": prompt}],
                model=self.default_model,
                temperature=0.7,
                max_tokens=150
            )
            
            content = response['choices'][0]['message']['content']
            result = json.loads(content)
            
            if result.get('card_type') and result.get('confidence', 0) >= 0.6:
                return {
                    "card_type": result['card_type'],
                    "topic": result['topic'],
                    "confidence": result['confidence']
                }
            return None
            
        except Exception:
            return None
    
    def _format_card_suggestion(self, suggested_card: Dict) -> str:
        """Format card suggestion message."""
        topic = suggested_card['topic']
        card_type = suggested_card['card_type']
        
        type_names = {
            'self': 'yourself',
            'character': 'this person',
            'world': 'this event'
        }
        
        return (
            f"It sounds like {topic} is important here. "
            f"Want me to create a card for {type_names.get(card_type, 'this')} "
            f"so I can remember it?"
        )
    
    async def _generate_natural_response(
        self,
        session_id: int,
        user_input: str
    ) -> str:
        """Generate natural conversational response."""
        transcript = self._get_session_transcript(session_id)
        
        prompt = f"""You're a warm, curious guide getting to know someone.

Conversation so far:
{transcript}

User just said: {user_input}

Respond naturally:
- Be conversational and warm
- Ask a follow-up question if something seems interesting
- Don't force topics or be clinical
- Keep it brief (1-2 sentences)

Response:"""
        
        try:
            response = await simple_llm_client.chat_completion(
                messages=[{"role": "system", "content": prompt}],
                model=self.default_model,
                temperature=0.8,
                max_tokens=100
            )
            return response['choices'][0]['message']['content']
        except Exception:
            return "Tell me more about that."
    
    async def _maybe_suggest_farm(self, session_id: int, client_id: int) -> bool:
        """
        Suggest farm discovery if appropriate (5+ sessions or interest).
        
        Returns True if suggestion was made.
        """
        # Count total sessions
        sessions = db.get_all_sessions_for_client(client_id)
        
        if len(sessions) >= 5:
            # Check if already suggested
            messages = db.get_session_messages(session_id)
            for msg in messages:
                if "garden" in msg.get('content', '').lower():
                    return False  # Already suggested
            
            suggestion = (
                "By the way, if you like, you can grow a little garden "
                "as you make progress. It's just for fun!"
            )
            
            db.add_message(
                session_id=session_id,
                role="assistant",
                content=suggestion,
                speaker="guide"
            )
            return True
        
        return False
    
    def _get_session_transcript(self, session_id: int) -> str:
        """Get conversation transcript."""
        messages = db.get_session_messages(session_id)
        return "\n".join([
            f"{msg.get('speaker', 'unknown')}: {msg.get('content', '')}"
            for msg in messages
        ])
    
    def _get_existing_cards_summary(self, session_id: int) -> str:
        """Get summary of existing cards."""
        session = db.get_session(session_id)
        client_id = session['client_id']
        
        parts = []
        
        self_card = db.get_self_card(client_id)
        if self_card:
            parts.append("Self card exists")
        
        char_cards = db.get_character_cards(client_id)
        for card in char_cards:
            parts.append(f"Character: {card['card_name']}")
        
        world_events = db.get_world_events(client_id)
        for event in world_events:
            parts.append(f"Life Event: {event['title']}")
        
        return "\n".join(parts) if parts else "No cards yet"
    
    def _get_guide_counselor_id(self) -> int:
        """Get or create guide counselor ID."""
        # Try to find existing "Guide" counselor
        counselors = db.get_all_counselors()
        for counselor in counselors:
            if counselor['name'] == 'Guide':
                return counselor['id']
        
        # Create Guide if not exists
        counselor_data = {
            'data': {
                'name': 'Guide',
                'specialization': 'Onboarding & Getting to Know You',
                'therapeutic_style': (
                    'Warm, curious, and conversational. '
                    'Helps users share what matters at their own pace.'
                ),
                'credentials': 'AI Guide'
            }
        }
        return db.create_counselor_profile(counselor_data)


# Global instance
guide_system = GuideSystem()